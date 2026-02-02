# -*- coding: utf-8 -*-
"""
Catalog tree builder for CVMFS visualization.

Traverses the catalog hierarchy and calculates cumulative download costs.
"""

from dataclasses import dataclass, field
from typing import List, Optional


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
            "children": [child.to_dict() for child in self.children],
        }


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
    ):
        """Initialize the tree builder.

        Args:
            repository: CVMFS repository object
            stop_threshold: Stop descending when catalog size exceeds this (bytes)
            max_depth: Maximum depth to traverse (None for unlimited)
        """
        self.repository = repository
        self.stop_threshold = stop_threshold
        self.max_depth = max_depth
        self._catalogs_downloaded = 0
        self._total_bytes_downloaded = 0

    def build(self) -> CatalogNode:
        """Build the catalog tree starting from the root.

        Returns:
            Root CatalogNode with populated children
        """
        revision = self.repository.get_current_revision()
        root_catalog = revision.retrieve_root_catalog()

        root_size = root_catalog.db_size()
        self._catalogs_downloaded = 1
        self._total_bytes_downloaded = root_size

        root_node = CatalogNode(
            path="/",
            hash=root_catalog.hash,
            size_bytes=root_size,
            cumulative_cost=root_size,
            depth=0,
            is_root=True,
            is_large=root_size > self.stop_threshold,
        )

        # Only descend if root is not too large and depth allows
        if not root_node.is_large and (self.max_depth is None or self.max_depth > 0):
            self._populate_children(root_node, root_catalog)

        return root_node

    def _populate_children(self, parent_node: CatalogNode, parent_catalog) -> None:
        """Recursively populate children of a catalog node.

        Args:
            parent_node: Parent CatalogNode to add children to
            parent_catalog: Parent Catalog object to query for nested catalogs
        """
        nested_refs = parent_catalog.list_nested()

        for ref in nested_refs:
            child_depth = parent_node.depth + 1

            # Check max depth
            if self.max_depth is not None and child_depth > self.max_depth:
                continue

            # Use size from CatalogReference if available (no download needed)
            child_size = ref.size if ref.size > 0 else 0
            child_cost = parent_node.cumulative_cost + child_size
            is_large = child_size > self.stop_threshold

            child_node = CatalogNode(
                path=ref.root_path,
                hash=ref.hash,
                size_bytes=child_size,
                cumulative_cost=child_cost,
                depth=child_depth,
                is_large=is_large,
            )

            parent_node.children.append(child_node)

            # Only descend into non-large catalogs
            if not is_large:
                # Need to download this catalog to get its children
                child_catalog = ref.retrieve_from(self.repository)
                self._catalogs_downloaded += 1
                self._total_bytes_downloaded += child_catalog.db_size()

                # Update size with actual value if it was 0
                if child_node.size_bytes == 0:
                    actual_size = child_catalog.db_size()
                    child_node.size_bytes = actual_size
                    child_node.cumulative_cost = (
                        parent_node.cumulative_cost + actual_size
                    )
                    child_node.is_large = actual_size > self.stop_threshold

                # Recurse if still not large
                if not child_node.is_large and (
                    self.max_depth is None or child_depth < self.max_depth
                ):
                    self._populate_children(child_node, child_catalog)

    @property
    def catalogs_downloaded(self) -> int:
        """Number of catalogs downloaded during tree building."""
        return self._catalogs_downloaded

    @property
    def total_bytes_downloaded(self) -> int:
        """Total bytes downloaded during tree building."""
        return self._total_bytes_downloaded
