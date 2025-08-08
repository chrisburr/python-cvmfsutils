#!/usr/bin/env python3

import cvmfs
import sys
import os
import os.path
import sqlite3
import time
import argparse

CACHE_VERSION = "v1"


def get_cache_path():
    path = os.environ.get("XDG_CACHE_HOME", "")
    if not path.strip():
        path = os.path.expanduser("~/.cache")
    path = os.path.join(path, "cvmfs-search", CACHE_VERSION)
    return path


CACHE_PATH = get_cache_path()


def index_repo(rev, output, enable_index=True):
    db = sqlite3.connect(output + ".tmp")

    # Create the catalog table.
    db.execute(
        """CREATE TABLE catalog (
            md5path_1 INTEGER,
            md5path_2 INTEGER,
            parent_1 INTEGER,
            parent_2 INTEGER,
            hash BLOB,
            name TEXT
        )"""
    ).close()

    if enable_index:
        # Create the indexes.
        db.execute(
            """
            CREATE INDEX catalog_hash
            ON catalog(hash);
            """
        ).close()
        db.execute(
            """
            CREATE INDEX catalog_md5path
            ON catalog(md5path_1, md5path_2);
            """
        ).close()

    for clg in rev.catalogs():
        print(clg)

        res = clg.run_sql(
            "SELECT md5path_1, md5path_2, parent_1, parent_2, hash, name FROM catalog"
        )

        for md5path_1, md5path_2, parent_1, parent_2, content_hash, name in res:
            db.execute(
                "INSERT INTO catalog(md5path_1, md5path_2, parent_1, parent_2, hash, name) VALUES (?, ?, ?, ?, ?, ?)",
                (md5path_1, md5path_2, parent_1, parent_2, content_hash, name),
            ).close()

    db.commit()

    db.close()

    print("finished indexing")

    time.sleep(5)

    os.rename(output + ".tmp", output)


def get_path(db: sqlite3.Connection, parent_1, parent_2):
    if parent_1 == 0 and parent_2 == 0:
        return ""

    results = db.execute(
        "SELECT parent_1, parent_2, name FROM catalog WHERE md5path_1 = ? AND md5path_2 = ? LIMIT 1",
        (parent_1, parent_2),
    )

    if results.rowcount == 0:
        raise Exception("not found")

    for parent_1, parent_2, name in results:
        parent = get_path(db, parent_1, parent_2)
        return os.path.join(parent, name)


def search_cvmfs_repo(url, enable_index=True):
    repo_url, data_hash = url.split("/data/")
    data_hash = data_hash.replace("/", "")

    repo = cvmfs.open_repository(repo_url)

    revision = repo.get_current_revision()

    database_cache = os.path.join(CACHE_PATH, revision.root_hash + ".db")
    if not os.path.exists(database_cache):
        print("indexing", repo_url)
        index_repo(revision, database_cache, enable_index=enable_index)

    content_hash = bytes.fromhex(data_hash)

    db = sqlite3.connect(database_cache)

    ret = []

    for parent_1, parent_2, name in db.execute(
        "SELECT parent_1, parent_2, name FROM catalog WHERE hash = ?",
        (content_hash,),
    ):
        path = get_path(db, parent_1, parent_2)
        ret.append(os.path.join(path, name))

    return ret


def main():
    parser = argparse.ArgumentParser(
        description="Search CVMFS repositories for all files matching a given download URL."
    )
    parser.add_argument("url", type=str, help="A CVMFS URL to print the paths for.")
    parser.add_argument(
        "--no-db-index",
        dest="db_index",
        action="store_false",
        default=True,
        help="Don't add indexes to the created SQLite database. If you use this the catalog will be created faster and take less disk space but searching will be slower.",
    )
    args = parser.parse_args()

    if not os.path.exists(CACHE_PATH):
        os.makedirs(CACHE_PATH)

    names = search_cvmfs_repo(args.url, args.db_index)
    for name in names:
        print(name)


if __name__ == "__main__":
    main()