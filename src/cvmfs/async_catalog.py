# -*- coding: utf-8 -*-
"""
Async catalog implementation using aiosqlite.

Provides non-blocking database access for CVMFS catalog files.
"""

import os
from dataclasses import dataclass
from typing import List, Optional

import aiosqlite


@dataclass
class AsyncCatalogReference:
    """Reference to a nested catalog."""

    root_path: str
    hash: str
    size: int = 0


class AsyncCatalog:
    """Async wrapper for CVMFS catalog database access.

    Uses aiosqlite for non-blocking database queries.
    """

    def __init__(self, db_path: str, catalog_hash: str = "", is_temp: bool = False):
        """Initialize catalog (use open() factory method instead)."""
        self._db_path = db_path
        self._db: Optional[aiosqlite.Connection] = None
        self._is_temp = is_temp
        self.hash = catalog_hash
        self.root_prefix = "/"
        self.schema = 0.0
        self.schema_revision = 0
        self._db_size: Optional[int] = None

    @classmethod
    async def open(cls, db_path: str, catalog_hash: str = "", is_temp: bool = False) -> "AsyncCatalog":
        """Open a catalog database asynchronously.

        Args:
            db_path: Path to the catalog database file
            catalog_hash: Hash of the catalog
            is_temp: If True, delete the file on close (for --no-cache mode)

        Returns:
            Initialized AsyncCatalog
        """
        catalog = cls(db_path, catalog_hash, is_temp=is_temp)
        await catalog._open_database()
        await catalog._read_properties()
        return catalog

    async def _open_database(self) -> None:
        """Open the sqlite database connection."""
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row

    async def close(self) -> None:
        """Close the database connection and clean up temp files."""
        if self._db:
            await self._db.close()
            self._db = None
        if self._is_temp and self._db_path:
            try:
                os.remove(self._db_path)
            except OSError:
                pass
            self._db_path = None

    async def __aenter__(self) -> "AsyncCatalog":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    def db_size(self) -> int:
        """Get the database file size."""
        if self._db_size is None:
            self._db_size = os.path.getsize(self._db_path)
        return self._db_size

    async def _read_properties(self) -> None:
        """Read catalog properties from the database."""
        async with self._db.execute(
            "SELECT key, value FROM properties"
        ) as cursor:
            async for row in cursor:
                key, value = row[0], row[1]
                if key == "schema":
                    self.schema = float(value)
                elif key == "schema_revision":
                    self.schema_revision = float(value)
                elif key == "root_prefix":
                    self.root_prefix = value

        if not hasattr(self, "schema_revision"):
            self.schema_revision = 0

    async def list_nested(self) -> List[AsyncCatalogReference]:
        """List all nested catalog references.

        Returns:
            List of AsyncCatalogReference objects
        """
        new_version = self.schema <= 1.2 and self.schema_revision > 0

        if new_version:
            sql = "SELECT path, sha1, size FROM nested_catalogs"
        else:
            sql = "SELECT path, sha1 FROM nested_catalogs"

        results = []
        async with self._db.execute(sql) as cursor:
            async for row in cursor:
                if new_version:
                    results.append(
                        AsyncCatalogReference(row[0], row[1], row[2])
                    )
                else:
                    results.append(AsyncCatalogReference(row[0], row[1]))

        return results

    def is_root(self) -> bool:
        """Check if this is the root catalog."""
        return self.root_prefix == "/"
