#!/usr/bin/env python3

import sys
import cvmfs
import os


def usage():
    print("Usage: big_catalogs <local repo name | remote repo url> [BIGNUM [BIGMB]]")
    print("  Lists all catalogs of the provided CVMFS repository with more than BIGNUM")
    print("  files in them, default 100000, or more than BIGMB megabytes, default 50.")


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        usage()
        sys.exit(1)

    repo_identifier = sys.argv[1]
    bignum = 100000
    bigmb = 50
    if len(sys.argv) > 2:
        bignum = int(sys.argv[2])
    if len(sys.argv) > 3:
        bigmb = int(sys.argv[3])

    repo = cvmfs.open_repository(repo_identifier)
    revision = repo.get_current_revision()
    for clg in revision.catalogs():
        res = clg.run_sql('SELECT count(*) FROM catalog;')
        num_entries = res[0][0]
        uncomp_mb = clg.db_size() / (1024*1024)
        if (num_entries > bignum) or (uncomp_mb >= bigmb):
            print(clg.root_prefix, num_entries, 'files',  uncomp_mb, 'MB')
        del res
        del clg


if __name__ == "__main__":
    main()