# -*- coding: utf-8 -*-
"""
Async repository wrapper for CVMFS.

Provides async access to CVMFS repositories using HTTP/2 for efficient
parallel catalog downloads.
"""

import io
from datetime import datetime
from typing import Optional, Tuple

import aiofiles
import dateutil.parser
from dateutil.tz import tzutc

from . import _common
from ._exceptions import RepositoryNotFound, FileNotFoundInRepository
from .async_fetcher import AsyncRemoteFetcher
from .async_catalog import AsyncCatalog
from .manifest import Manifest


class AsyncRepository:
    """Async wrapper around a CVMFS Repository.

    Uses AsyncRemoteFetcher for HTTP/2 multiplexed downloads and
    AsyncCatalog for non-blocking database access.
    """

    def __init__(self, fetcher: AsyncRemoteFetcher):
        """Initialize with an async fetcher.

        Use AsyncRepository.open() factory method instead of calling directly.
        """
        self._fetcher = fetcher
        self._opened_catalogs = {}
        self.manifest: Optional[Manifest] = None
        self.fqrn: Optional[str] = None
        self.last_replication: Optional[datetime] = None
        self.replicating = False
        self.replicating_since: Optional[datetime] = None
        self.type = "unknown"

    @classmethod
    async def open(
        cls,
        repo_url: str,
        cache_dir: Optional[str] = None,
        max_concurrency: int = AsyncRemoteFetcher.DEFAULT_CONCURRENCY,
    ) -> "AsyncRepository":
        """Open a remote repository asynchronously.

        Args:
            repo_url: URL of the CVMFS repository (must start with http://)
            cache_dir: Directory for disk cache (None for no caching)
            max_concurrency: Maximum concurrent HTTP requests

        Returns:
            Initialized AsyncRepository

        Raises:
            RepositoryNotFound: If repository cannot be opened
            ValueError: If repo_url is not a remote URL
        """
        if not repo_url.startswith("http://") and not repo_url.startswith("https://"):
            raise ValueError(
                f"AsyncRepository only supports remote URLs, got: {repo_url}"
            )

        fetcher = AsyncRemoteFetcher(repo_url, cache_dir, max_concurrency)
        repo = cls(fetcher)
        await repo._initialize()
        return repo

    async def __aenter__(self) -> "AsyncRepository":
        """Enter async context."""
        await self._fetcher.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - close the fetcher and catalogs."""
        for catalog in self._opened_catalogs.values():
            await catalog.close()
        self._opened_catalogs.clear()
        await self._fetcher.__aexit__(exc_type, exc_val, exc_tb)

    async def close(self) -> None:
        """Close the repository, catalogs, and fetcher."""
        for catalog in self._opened_catalogs.values():
            await catalog.close()
        self._opened_catalogs.clear()
        await self._fetcher.close()

    async def _initialize(self) -> None:
        """Initialize the repository by reading manifest and metadata."""
        await self._read_manifest()
        await self._try_to_get_last_replication_timestamp()
        await self._try_to_get_replication_state()

    async def _read_manifest(self) -> None:
        """Read and parse the repository manifest."""
        try:
            manifest_path, _ = await self._fetcher.retrieve_raw_file(
                _common._MANIFEST_NAME
            )
            async with aiofiles.open(manifest_path, "rb") as f:
                content = await f.read()
            # Manifest expects a file-like object with sync methods
            self.manifest = Manifest(io.BytesIO(content))
            self.fqrn = self.manifest.repository_name
        except FileNotFoundInRepository:
            raise RepositoryNotFound(self._fetcher.source)

    @staticmethod
    def _read_timestamp(timestamp_string: bytes) -> datetime:
        """Parse a timestamp string to datetime."""
        if isinstance(timestamp_string, bytes):
            timestamp_string = timestamp_string.decode()
        local_ts = dateutil.parser.parse(
            timestamp_string.strip(),
            ignoretz=False,
            tzinfos=_common.TzInfos.get_tzinfos(),
        )
        return local_ts.astimezone(tzutc())

    async def _try_to_get_last_replication_timestamp(self) -> None:
        """Try to read the last replication timestamp."""
        try:
            path, _ = await self._fetcher.retrieve_raw_file(
                _common._LAST_REPLICATION_NAME
            )
            async with aiofiles.open(path, "rb") as f:
                timestamp = await f.readline()
            self.last_replication = self._read_timestamp(timestamp)
            if not self._has_repository_type():
                self.type = "stratum1"
        except FileNotFoundInRepository:
            self.last_replication = datetime.fromtimestamp(0, tz=tzutc())

    async def _try_to_get_replication_state(self) -> None:
        """Try to read the replication state."""
        self.replicating = False
        try:
            path, _ = await self._fetcher.retrieve_raw_file(_common._REPLICATING_NAME)
            async with aiofiles.open(path, "rb") as f:
                timestamp = await f.readline()
            self.replicating = True
            self.replicating_since = self._read_timestamp(timestamp)
        except FileNotFoundInRepository:
            pass

    def _has_repository_type(self) -> bool:
        """Check if repository type is known."""
        return hasattr(self, "type") and self.type != "unknown"

    def get_root_hash(self) -> str:
        """Get the root catalog hash from the manifest."""
        return self.manifest.root_catalog

    async def retrieve_catalog(self, catalog_hash: str) -> Tuple[AsyncCatalog, bool]:
        """Download and open a catalog from the repository.

        Args:
            catalog_hash: Hash of the catalog to retrieve

        Returns:
            Tuple of (AsyncCatalog object, was_cached)
        """
        if catalog_hash in self._opened_catalogs:
            return self._opened_catalogs[catalog_hash], True

        catalog, was_cached = await self._retrieve_and_open_catalog(catalog_hash)
        return catalog, was_cached

    async def get_object_size(
        self, object_hash: str, hash_suffix: str = ""
    ) -> Optional[int]:
        """Get the compressed size of an object without downloading it.

        Args:
            object_hash: Hash of the object
            hash_suffix: Optional suffix

        Returns:
            Size in bytes, or None if cannot be determined
        """
        path = f"data/{object_hash[:2]}/{object_hash[2:]}{hash_suffix}"
        return await self._fetcher.get_file_size(path)

    async def _retrieve_and_open_catalog(
        self, catalog_hash: str
    ) -> Tuple[AsyncCatalog, bool]:
        """Retrieve a catalog file and open it.

        Args:
            catalog_hash: Hash of the catalog

        Returns:
            Tuple of (AsyncCatalog object, was_cached)
        """
        path = f"data/{catalog_hash[:2]}/{catalog_hash[2:]}C"
        catalog_path, was_cached = await self._fetcher.retrieve_file(path)
        new_catalog = await AsyncCatalog.open(catalog_path, catalog_hash)
        self._opened_catalogs[catalog_hash] = new_catalog
        return new_catalog, was_cached

    async def close_catalog(self, catalog: AsyncCatalog) -> None:
        """Close a catalog and remove it from the opened catalogs cache."""
        try:
            await catalog.close()
            del self._opened_catalogs[catalog.hash]
        except KeyError:
            pass
