# -*- coding: utf-8 -*-
"""
Async HTTP fetcher using httpx with HTTP/2 support.

This module provides an asynchronous fetcher that leverages HTTP/2 connection
multiplexing for efficient parallel downloads of CVMFS catalog files.
"""

import asyncio
import logging
import os
import tempfile
import zlib
from typing import Optional, Tuple

import aiofiles
import aiofiles.os
import httpx

import cvmfs
from ._exceptions import FileNotFoundInRepository

logger = logging.getLogger(__name__)


class AsyncRemoteFetcher:
    """Async HTTP fetcher with HTTP/2 support and connection pooling.

    Uses a single httpx.AsyncClient with HTTP/2 enabled to multiplex
    many concurrent requests over a single TCP connection.
    """

    DEFAULT_CONCURRENCY = 100
    MAX_RETRIES = 3
    RETRY_BACKOFF = 1.0  # Base delay in seconds

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
            max_concurrency: Maximum concurrent requests (default: 100)
        """
        self.source = repo_url
        self._cache_dir = cache_dir
        self._max_concurrency = max_concurrency
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._client: Optional[httpx.AsyncClient] = None
        self._user_agent = f"{cvmfs.__package_name__}/{cvmfs.__version__}"

        # Create cache directory structure
        if cache_dir:
            self._create_cache_structure()

    def _create_cache_structure(self) -> None:
        """Create the cache directory structure."""
        os.makedirs(os.path.join(self._cache_dir, "data", "txn"), exist_ok=True)
        for i in range(0x00, 0xFF + 1):
            folder = f"{i:02x}"
            os.makedirs(
                os.path.join(self._cache_dir, "data", folder), exist_ok=True
            )

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
        return self._cache_dir

    def _get_cached_path(self, file_name: str) -> Optional[str]:
        """Get the path to a cached file if it exists.

        Args:
            file_name: Name of the file in the cache

        Returns:
            Full path if cached, None otherwise
        """
        if not self._cache_dir:
            return None
        full_path = os.path.join(self._cache_dir, file_name)
        if os.path.exists(full_path):
            return full_path
        return None

    async def retrieve_file(self, file_name: str) -> Tuple[str, bool]:
        """Retrieve a file, decompressing it.

        Args:
            file_name: Name of the file in the repository

        Returns:
            Tuple of (path to cached file, was_cached)

        Raises:
            FileNotFoundInRepository: If the file doesn't exist
        """
        return await self._retrieve(file_name, decompress=True)

    async def retrieve_raw_file(self, file_name: str) -> Tuple[str, bool]:
        """Retrieve a file without decompression.

        Args:
            file_name: Name of the file in the repository

        Returns:
            Tuple of (path to cached file, was_cached)

        Raises:
            FileNotFoundInRepository: If the file doesn't exist
        """
        return await self._retrieve(file_name, decompress=False)

    async def _retrieve(self, file_name: str, decompress: bool) -> Tuple[str, bool]:
        """Internal method to retrieve a file.

        Args:
            file_name: Name of the file in the repository
            decompress: Whether to decompress the file content

        Returns:
            Tuple of (path to file, was_cached)
        """
        # Check cache first
        cached_path = self._get_cached_path(file_name)
        if cached_path:
            return cached_path, True

        # Download from remote with retry logic
        await self._ensure_client()
        file_url = self._make_file_uri(file_name)

        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                async with self._semaphore:
                    response = await self._client.get(file_url)

                    if response.status_code == 404:
                        raise FileNotFoundInRepository(file_url)

                    if response.status_code != 200:
                        raise httpx.HTTPStatusError(
                            f"HTTP {response.status_code}",
                            request=response.request,
                            response=response,
                        )

                    content = response.content
                    break  # Success

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise FileNotFoundInRepository(file_url) from e
                last_error = e
            except httpx.RequestError as e:
                last_error = e

            # Retry with exponential backoff
            if attempt < self.MAX_RETRIES - 1:
                delay = self.RETRY_BACKOFF * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d for %s after error: %s (waiting %.1fs)",
                    attempt + 1,
                    self.MAX_RETRIES,
                    file_url,
                    last_error,
                    delay,
                )
                await asyncio.sleep(delay)
        else:
            # All retries failed
            raise FileNotFoundInRepository(file_url) from last_error

        if decompress:
                content = zlib.decompress(content)

        # Write to cache
        if self._cache_dir:
            full_path = os.path.join(self._cache_dir, file_name)
            tmp_dir = os.path.join(self._cache_dir, "data", "txn")

            # Write to temp file then rename (atomic)
            fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, prefix="tmp.")
            try:
                async with aiofiles.open(fd, "wb", closefd=True) as f:
                    await f.write(content)
                await aiofiles.os.rename(tmp_path, full_path)
            except Exception:
                try:
                    await aiofiles.os.remove(tmp_path)
                except (IOError, OSError):
                    pass
                raise

            return full_path, False
        else:
            # No cache - write to temp file
            fd, tmp_path = tempfile.mkstemp(prefix="cvmfs_")
            async with aiofiles.open(fd, "wb", closefd=True) as f:
                await f.write(content)
            return tmp_path, False

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
