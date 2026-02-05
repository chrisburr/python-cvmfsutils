# -*- coding: utf-8 -*-
"""
Async cache implementation using aiofiles.

Provides non-blocking file I/O for caching downloaded catalog files.
"""

import os
import tempfile
from typing import Optional, Tuple

import aiofiles
import aiofiles.os


class AsyncDiskCache:
    """Async disk cache using aiofiles for non-blocking I/O."""

    def __init__(self, cache_dir: str):
        """Initialize the async cache.

        Args:
            cache_dir: Directory for cached files (must exist)
        """
        self._cache_dir = cache_dir

    def get_cache_path(self) -> str:
        """Get the cache directory path."""
        return self._cache_dir

    def _get_full_path(self, file_name: str) -> str:
        """Get the full path for a cached file."""
        return os.path.join(self._cache_dir, file_name)

    async def get(self, file_name: str) -> Optional[bytes]:
        """Get a file from cache if it exists.

        Args:
            file_name: Name of the file in the cache

        Returns:
            File contents as bytes, or None if not cached
        """
        full_path = self._get_full_path(file_name)
        try:
            if await aiofiles.os.path.exists(full_path):
                async with aiofiles.open(full_path, "rb") as f:
                    return await f.read()
        except (IOError, OSError):
            pass
        return None

    async def put(self, file_name: str, content: bytes) -> str:
        """Store content in the cache.

        Args:
            file_name: Name for the cached file
            content: Content to cache

        Returns:
            Full path to the cached file
        """
        full_path = self._get_full_path(file_name)

        # Write to temp file first, then rename (atomic on POSIX)
        tmp_dir = os.path.join(self._cache_dir, "data", "txn")
        fd, tmp_path = tempfile.mkstemp(dir=tmp_dir, prefix="tmp.")
        try:
            async with aiofiles.open(fd, "wb", closefd=True) as f:
                await f.write(content)
            await aiofiles.os.rename(tmp_path, full_path)
        except Exception:
            # Clean up temp file on error
            try:
                await aiofiles.os.remove(tmp_path)
            except (IOError, OSError):
                pass
            raise

        return full_path

    def get_sync(self, file_name: str) -> Optional[str]:
        """Synchronously check if file exists and return path.

        Used for checking cache without async overhead.

        Args:
            file_name: Name of the file in the cache

        Returns:
            Full path if file exists, None otherwise
        """
        full_path = self._get_full_path(file_name)
        if os.path.exists(full_path):
            return full_path
        return None
