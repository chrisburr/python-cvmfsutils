# -*- coding: utf-8 -*-
"""
Catalog tree builder for CVMFS visualization.

Traverses the catalog hierarchy and calculates cumulative download costs.
"""

import os
import queue
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class CatalogNode:
    """Represents a node in the catalog hierarchy tree."""

    path: str
    hash: str
    size_bytes: int
    cumulative_cost: int
    depth: int
    children: List["CatalogNode"] = field(default_factory=list)
    is_large: bool = False
    is_root: bool = False
    is_virtual: bool = False  # True for intermediate path nodes without a catalog

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "path": self.path,
            "name": self.path.split("/")[-1] or "/",
            "hash": self.hash,
            "size": self.size_bytes,
            "cumulative_cost": self.cumulative_cost,
            "depth": self.depth,
            "is_large": self.is_large,
            "is_root": self.is_root,
            "is_virtual": self.is_virtual,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CatalogNode":
        """Construct a CatalogNode from a dictionary (inverse of to_dict())."""
        return cls(
            path=data["path"],
            hash=data["hash"],
            size_bytes=data["size"],
            cumulative_cost=data["cumulative_cost"],
            depth=data["depth"],
            children=[cls.from_dict(c) for c in data.get("children", [])],
            is_large=data.get("is_large", False),
            is_root=data.get("is_root", False),
            is_virtual=data.get("is_virtual", False),
        )

    def find_or_create_child(self, path_segment: str, full_path: str, depth: int) -> "CatalogNode":
        """Find existing child with path or create a virtual intermediate node."""
        for child in self.children:
            if child.path == full_path:
                return child
            # Check if this child is along the path
            if full_path.startswith(child.path + "/"):
                return child

        # Create virtual intermediate node
        virtual = CatalogNode(
            path=full_path,
            hash="",
            size_bytes=0,
            cumulative_cost=self.cumulative_cost,
            depth=depth,
            is_virtual=True,
        )
        self.children.append(virtual)
        return virtual


def build_lookup(node: CatalogNode) -> Dict[str, CatalogNode]:
    """Build a path->node lookup dict via BFS for O(1) access."""
    lookup: Dict[str, CatalogNode] = {}
    queue_nodes = deque([node])
    while queue_nodes:
        current = queue_nodes.popleft()
        if not current.is_virtual:
            lookup[current.path] = current
        queue_nodes.extend(current.children)
    return lookup


def count_nodes(node: CatalogNode) -> int:
    """Count non-virtual nodes in a subtree."""
    count = 0
    stack = [node]
    while stack:
        current = stack.pop()
        if not current.is_virtual:
            count += 1
        stack.extend(current.children)
    return count


def recalculate_tree(root: CatalogNode) -> None:
    """Fix cumulative_cost and depth for all nodes top-down.

    Needed because grafted subtrees have stale values from the
    previous tree's parent chain.
    """
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        if parent is None:
            # Root node: depth 0, cost = own size
            node.depth = 0
            node.cumulative_cost = node.size_bytes
        else:
            node.depth = parent.depth + 1
            node.cumulative_cost = parent.cumulative_cost + node.size_bytes
        for child in node.children:
            stack.append((child, node))


class CatalogTreeBuilder:
    """Builds a tree of catalog nodes with cost calculations.

    Traverses the CVMFS catalog hierarchy, calculating the cumulative
    download cost to reach each catalog. Uses intelligent stopping to
    avoid descending into large catalogs.
    """

    DEFAULT_STOP_THRESHOLD = 2 * 1024 * 1024  # 2 MB

    def __init__(
        self,
        repository,
        stop_threshold: int = DEFAULT_STOP_THRESHOLD,
        max_depth: Optional[int] = None,
        ignore_paths: Optional[List[str]] = None,
        progress_callback: Optional[Callable[[dict], None]] = None,
        max_workers: int = 1,
        previous_tree: Optional[CatalogNode] = None,
    ):
        """Initialize the tree builder.

        Args:
            repository: CVMFS repository object
            stop_threshold: Stop descending when catalog size exceeds this (bytes)
            max_depth: Maximum depth to traverse (None for unlimited)
            ignore_paths: List of path prefixes to ignore (e.g., ["/lib/var"])
            progress_callback: Optional callback function called during traversal.
                Receives a dict with keys: path, catalogs_downloaded,
                bytes_downloaded, catalogs_found, large_catalogs_found
            max_workers: Number of parallel workers for downloading catalogs
            previous_tree: Optional CatalogNode tree from a previous run for caching
        """
        self.repository = repository
        self.stop_threshold = stop_threshold
        self.max_depth = max_depth
        self.ignore_paths = ignore_paths or []
        self.progress_callback = progress_callback
        self.max_workers = max_workers
        self._previous_tree = previous_tree
        self._previous_lookup = build_lookup(previous_tree) if previous_tree else {}
        self._lock = threading.Lock()
        self._catalogs_downloaded = 0
        self._total_bytes_downloaded = 0
        self._catalogs_found = 0
        self._large_catalogs_found = 0
        self._head_requests = 0
        self._bytes_skipped = 0
        self._ignored_count = 0
        self._cache_hits = 0
        self._bytes_from_cache = 0
        self._tree_cache_reused = 0

    def build(self) -> CatalogNode:
        """Build the catalog tree starting from the root.

        Returns:
            Root CatalogNode with populated children
        """
        revision = self.repository.get_current_revision()

        # Check if root hash matches previous tree (zero downloads needed)
        root_hash = revision.root_hash
        if self._previous_tree and self._previous_tree.hash == root_hash:
            self._tree_cache_reused = count_nodes(self._previous_tree)
            recalculate_tree(self._previous_tree)
            return self._previous_tree

        # Check if root catalog is in cache before retrieving
        root_in_cache = self._is_catalog_in_cache(root_hash)

        root_catalog = revision.retrieve_root_catalog()

        root_size = root_catalog.db_size()
        self._catalogs_downloaded = 1
        self._total_bytes_downloaded = root_size
        self._catalogs_found = 1

        if root_in_cache:
            self._cache_hits = 1
            self._bytes_from_cache = root_size

        is_large = root_size > self.stop_threshold
        if is_large:
            self._large_catalogs_found = 1

        self._report_progress("/")

        root_node = CatalogNode(
            path="/",
            hash=root_catalog.hash,
            size_bytes=root_size,
            cumulative_cost=root_size,
            depth=0,
            is_root=True,
            is_large=is_large,
        )

        # Only descend if root is not too large and depth allows
        if not root_node.is_large and (self.max_depth is None or self.max_depth > 0):
            self._populate_children(root_node, root_catalog)

        recalculate_tree(root_node)
        return root_node

    def _should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored based on ignore_paths."""
        for ignore_prefix in self.ignore_paths:
            if path == ignore_prefix or path.startswith(ignore_prefix + "/"):
                return True
        return False

    def _report_progress(self, path: str) -> None:
        """Report progress via callback if available."""
        if self.progress_callback:
            self.progress_callback(
                {
                    "path": path,
                    "catalogs_downloaded": self._catalogs_downloaded,
                    "bytes_downloaded": self._total_bytes_downloaded,
                    "catalogs_found": self._catalogs_found,
                    "large_catalogs_found": self._large_catalogs_found,
                    "head_requests": self._head_requests,
                    "bytes_skipped": self._bytes_skipped,
                    "cache_hits": self._cache_hits,
                    "bytes_from_cache": self._bytes_from_cache,
                }
            )

    def _is_catalog_in_cache(self, catalog_hash: str) -> bool:
        """Check if a catalog exists in the disk cache."""
        cache_path = self.repository._fetcher.get_cache_path()
        if not cache_path:
            return False
        file_path = os.path.join(
            cache_path, "data", catalog_hash[:2], catalog_hash[2:] + "C"
        )
        return os.path.exists(file_path)

    def _get_catalog_size(self, catalog_hash: str, ref_size: int) -> int:
        """Get catalog size, using HEAD request if ref_size is unknown.

        Args:
            catalog_hash: The catalog's hash
            ref_size: Size from CatalogReference (0 if unknown)

        Returns:
            Estimated size in bytes (compressed size from HEAD as lower bound,
            or uncompressed size from ref if available)
        """
        if ref_size > 0:
            return ref_size

        # Size unknown, use HEAD request to get compressed size
        with self._lock:
            self._head_requests += 1
        compressed_size = self.repository.get_object_size(catalog_hash, "C")
        if compressed_size is not None:
            return compressed_size

        # Couldn't determine size, return 0 (will download to find out)
        return 0

    def _get_path_segments(self, parent_path: str, child_path: str) -> List[str]:
        """Get the intermediate path segments between parent and child.

        For parent "/" and child "/lib/lcg/releases", returns:
        ["/lib", "/lib/lcg", "/lib/lcg/releases"]
        """
        if parent_path == "/":
            parent_path = ""

        # Get the relative part
        if not child_path.startswith(parent_path):
            return [child_path]

        relative = child_path[len(parent_path):]
        if relative.startswith("/"):
            relative = relative[1:]

        parts = relative.split("/")
        segments = []
        current = parent_path

        for part in parts:
            current = current + "/" + part if current else "/" + part
            segments.append(current)

        return segments

    def _insert_at_path(
        self,
        root_node: CatalogNode,
        parent_path: str,
        catalog_path: str,
        catalog_hash: str,
        catalog_size: int,
        is_large: bool,
    ) -> CatalogNode:
        """Insert a catalog node at the correct path location.

        Creates intermediate virtual nodes as needed for path gaps.
        """
        segments = self._get_path_segments(parent_path, catalog_path)

        current = root_node
        for i, seg_path in enumerate(segments):
            is_final = i == len(segments) - 1
            seg_depth = current.depth + 1

            if is_final:
                # This is the actual catalog node
                child_cost = current.cumulative_cost + catalog_size
                child_node = CatalogNode(
                    path=catalog_path,
                    hash=catalog_hash,
                    size_bytes=catalog_size,
                    cumulative_cost=child_cost,
                    depth=seg_depth,
                    is_large=is_large,
                )
                current.children.append(child_node)
                return child_node
            else:
                # Find or create intermediate node
                current = current.find_or_create_child(
                    seg_path.split("/")[-1], seg_path, seg_depth
                )

        return current

    def _graft_at_path(
        self,
        root_node: CatalogNode,
        parent_path: str,
        cached_node: CatalogNode,
    ) -> CatalogNode:
        """Graft a cached subtree at the correct path location.

        Like _insert_at_path but appends the cached node (with all children)
        instead of creating a new node.
        """
        segments = self._get_path_segments(parent_path, cached_node.path)

        current = root_node
        for i, seg_path in enumerate(segments):
            is_final = i == len(segments) - 1

            if is_final:
                current.children.append(cached_node)
                return cached_node
            else:
                seg_depth = current.depth + 1
                current = current.find_or_create_child(
                    seg_path.split("/")[-1], seg_path, seg_depth
                )

        return current

    def _process_single_ref(self, parent_node: CatalogNode, ref):
        """Process a single catalog reference.

        Returns:
            Tuple of (child_node, child_catalog) if should recurse, else (child_node, None)
        """
        # Check if this path should be ignored
        if self._should_ignore(ref.root_path):
            with self._lock:
                self._ignored_count += 1
            return None, None

        # Check previous tree cache before downloading
        cached_node = self._previous_lookup.get(ref.root_path)
        if cached_node is not None and cached_node.hash == ref.hash:
            reused = count_nodes(cached_node)
            with self._lock:
                self._tree_cache_reused += reused
                self._catalogs_found += reused
                grafted = self._graft_at_path(
                    parent_node, parent_node.path, cached_node
                )
            return grafted, None

        with self._lock:
            self._catalogs_found += 1

        # Get size - use HEAD request if ref.size is 0
        child_size = self._get_catalog_size(ref.hash, ref.size)
        is_large = child_size > self.stop_threshold

        if is_large:
            with self._lock:
                self._large_catalogs_found += 1
                self._bytes_skipped += child_size

        # Insert at correct path location, creating intermediate nodes
        with self._lock:
            child_node = self._insert_at_path(
                parent_node,
                parent_node.path,
                ref.root_path,
                ref.hash,
                child_size,
                is_large,
            )

        # Check max depth based on actual tree depth
        if self.max_depth is not None and child_node.depth > self.max_depth:
            return child_node, None

        # Only descend into non-large catalogs
        if not is_large:
            # Check if in cache before retrieving
            in_cache = self._is_catalog_in_cache(ref.hash)

            # Need to download this catalog to get its children
            child_catalog = ref.retrieve_from(self.repository)

            with self._lock:
                self._catalogs_downloaded += 1
                catalog_size = child_catalog.db_size()
                self._total_bytes_downloaded += catalog_size

                if in_cache:
                    self._cache_hits += 1
                    self._bytes_from_cache += catalog_size

            self._report_progress(ref.root_path)

            # Update size with actual value if it was 0
            if child_node.size_bytes == 0:
                actual_size = child_catalog.db_size()
                with self._lock:
                    child_node.size_bytes = actual_size
                    child_node.cumulative_cost = (
                        child_node.cumulative_cost -
                        child_node.size_bytes + actual_size
                    )
                    child_node.is_large = actual_size > self.stop_threshold
                    if child_node.is_large:
                        self._large_catalogs_found += 1

            # Return catalog for recursion if still not large and within depth
            if not child_node.is_large and (
                self.max_depth is None or child_node.depth < self.max_depth
            ):
                return child_node, child_catalog

        return child_node, None

    def _populate_children(self, root_node: CatalogNode, root_catalog) -> None:
        """Populate all children using a work queue for true parallelism.

        Uses a queue-based approach where workers process catalogs and add
        newly discovered children to the queue, keeping all workers busy.

        Args:
            root_node: Root CatalogNode to start from
            root_catalog: Root Catalog object to query for nested catalogs
        """
        if self.max_workers <= 1:
            # Single-threaded mode - use simple recursion
            self._populate_children_sequential(root_node, root_catalog)
            return

        # Work queue holds (parent_node, parent_catalog) tuples
        work_queue = queue.Queue()
        work_queue.put((root_node, root_catalog))

        # Track active workers to know when we're done
        active_workers = threading.Semaphore(0)
        items_in_flight = [1]  # Use list to allow modification in nested function
        items_lock = threading.Lock()

        def worker():
            while True:
                try:
                    # Wait for work with timeout to allow checking for completion
                    try:
                        parent_node, parent_catalog = work_queue.get(timeout=0.1)
                    except queue.Empty:
                        # Check if we should exit (no more work coming)
                        with items_lock:
                            if items_in_flight[0] == 0:
                                return
                        continue

                    # Process this catalog's nested refs
                    nested_refs = parent_catalog.list_nested()

                    for ref in nested_refs:
                        child_node, child_catalog = self._process_single_ref(parent_node, ref)
                        if child_catalog is not None:
                            with items_lock:
                                items_in_flight[0] += 1
                            work_queue.put((child_node, child_catalog))

                    # Mark this item as done
                    with items_lock:
                        items_in_flight[0] -= 1

                except Exception as e:
                    # Don't let worker die on error
                    with items_lock:
                        items_in_flight[0] -= 1

        # Start worker threads
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(worker) for _ in range(self.max_workers)]

            # Wait for all workers to complete
            for future in futures:
                future.result()

    def _populate_children_sequential(self, parent_node: CatalogNode, parent_catalog) -> None:
        """Sequential version of populate_children for single-threaded mode."""
        nested_refs = parent_catalog.list_nested()

        if not nested_refs:
            return

        for ref in nested_refs:
            child_node, child_catalog = self._process_single_ref(parent_node, ref)
            if child_catalog is not None:
                self._populate_children_sequential(child_node, child_catalog)

    @property
    def catalogs_downloaded(self) -> int:
        """Number of catalogs downloaded during tree building."""
        return self._catalogs_downloaded

    @property
    def total_bytes_downloaded(self) -> int:
        """Total bytes downloaded during tree building."""
        return self._total_bytes_downloaded

    @property
    def catalogs_found(self) -> int:
        """Total number of catalogs found (including those not downloaded)."""
        return self._catalogs_found

    @property
    def large_catalogs_found(self) -> int:
        """Number of large catalogs found (exploration stopped)."""
        return self._large_catalogs_found

    @property
    def head_requests(self) -> int:
        """Number of HEAD requests made to check catalog sizes."""
        return self._head_requests

    @property
    def bytes_skipped(self) -> int:
        """Total bytes skipped by not downloading large catalogs."""
        return self._bytes_skipped

    @property
    def ignored_count(self) -> int:
        """Number of catalogs ignored due to ignore_paths."""
        return self._ignored_count

    @property
    def cache_hits(self) -> int:
        """Number of catalogs retrieved from cache."""
        return self._cache_hits

    @property
    def bytes_from_cache(self) -> int:
        """Total bytes retrieved from cache."""
        return self._bytes_from_cache

    @property
    def tree_cache_reused(self) -> int:
        """Number of catalog nodes reused from previous tree cache."""
        return self._tree_cache_reused
