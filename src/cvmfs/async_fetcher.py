# -*- coding: utf-8 -*-
"""
Async HTTP fetcher using httpx with HTTP/2 support.

This module provides an asynchronous fetcher that leverages HTTP/2 connection
multiplexing for efficient parallel downloads of CVMFS catalog files.
"""

import asyncio
import os
import zlib
from typing import List, Optional, Tuple

import httpx

import cvmfs
from .cache import DiskCache, DummyCache
from ._exceptions import FileNotFoundInRepository


class AsyncRemoteFetcher:
    """Async HTTP fetcher with HTTP/2 support and connection pooling.

    Uses a single httpx.AsyncClient with HTTP/2 enabled to multiplex
    many concurrent requests over a single TCP connection.
    """

    DEFAULT_CONCURRENCY = 50

    def __init__(
        self,
        repo_url: str,
        cache_dir: Optional[str] = None,
        max_concurrency: int = DEFAULT_CONCURRENCY,
    ):
        """Initialize the async fetcher.

        Args:
            repo_url: Base URL of the CVMFS repository
            cache_dir: Directory for disk cache (None for no caching)
            max_concurrency: Maximum concurrent requests (default: 50)
        """
        self.source = repo_url
        self._cache = DiskCache(cache_dir) if cache_dir else DummyCache()
        self._max_concurrency = max_concurrency
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._user_agent = f"{cvmfs.__package_name__}/{cvmfs.__version__}"

    async def __aenter__(self) -> "AsyncRemoteFetcher":
        """Enter async context - create HTTP client."""
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit async context - close HTTP client."""
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure the HTTP client and semaphore are created."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self._max_concurrency)

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _make_file_uri(self, file_name: str) -> str:
        """Construct the full URL for a file."""
        return os.path.join(self.source, file_name)

    def get_cache_path(self) -> Optional[str]:
        """Get the cache directory path."""
        if self._cache:
            return self._cache.get_cache_path()
        return None

    def _is_cached(self, file_name: str) -> bool:
        """Check if a file exists in the cache."""
        cached = self._cache.get(file_name)
        if cached:
            cached.close()
            return True
        return False

    async def retrieve_file(self, file_name: str) -> Tuple[any, bool]:
        """Retrieve a file, decompressing it.

        Args:
            file_name: Name of the file in the repository

        Returns:
            Tuple of (file object, was_cached)

        Raises:
            FileNotFoundInRepository: If the file doesn't exist
        """
        return await self._retrieve(file_name, decompress=True)

    async def retrieve_raw_file(self, file_name: str) -> Tuple[any, bool]:
        """Retrieve a file without decompression.

        Args:
            file_name: Name of the file in the repository

        Returns:
            Tuple of (file object, was_cached)

        Raises:
            FileNotFoundInRepository: If the file doesn't exist
        """
        return await self._retrieve(file_name, decompress=False)

    async def _retrieve(self, file_name: str, decompress: bool) -> Tuple[any, bool]:
        """Internal method to retrieve a file.

        Args:
            file_name: Name of the file in the repository
            decompress: Whether to decompress the file content

        Returns:
            Tuple of (file object, was_cached)
        """
        # Check cache first
        cached_file_ro = self._cache.get(file_name)
        if cached_file_ro:
            return cached_file_ro, True

        # Download from remote
        await self._ensure_client()

        async with self._semaphore:
            file_url = self._make_file_uri(file_name)

            try:
                response = await self._client.get(file_url)
            except httpx.RequestError as e:
                raise FileNotFoundInRepository(file_url) from e

            if response.status_code != 200:
                raise FileNotFoundInRepository(file_url)

            content = response.content
            if decompress:
                content = zlib.decompress(content)

        # Write to cache
        cached_file_rw = self._cache.transaction(file_name)
        cached_file_rw.write(content)
        return self._cache.commit(cached_file_rw), False

    async def retrieve_files_batch(
        self,
        file_names: List[str],
        decompress: bool = True,
    ) -> List[Tuple[str, any, bool]]:
        """Retrieve multiple files concurrently.

        Args:
            file_names: List of file names to retrieve
            decompress: Whether to decompress the files

        Returns:
            List of (file_name, file_object, was_cached) tuples
        """
        async def fetch_one(file_name: str) -> Tuple[str, any, bool]:
            file_obj, was_cached = await self._retrieve(file_name, decompress)
            return file_name, file_obj, was_cached

        tasks = [fetch_one(fn) for fn in file_names]
        return await asyncio.gather(*tasks)

    async def get_file_size(self, file_name: str) -> Optional[int]:
        """Get the compressed file size via HEAD request.

        Args:
            file_name: Name of the file in the repository

        Returns:
            Size in bytes, or None if size cannot be determined
        """
        await self._ensure_client()

        async with self._semaphore:
            file_url = self._make_file_uri(file_name)

            try:
                response = await self._client.head(file_url)
                if response.status_code == 200:
                    content_length = response.headers.get("content-length")
                    if content_length:
                        return int(content_length)
            except httpx.RequestError:
                pass

        return None
