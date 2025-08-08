#!/usr/bin/env python3

import argparse
import cvmfs
import os


def main():
    parser = argparse.ArgumentParser(
        description="Lists all catalogs of the provided CVMFS repository with more than BIGNUM files in them or more than BIGMB megabytes."
    )
    parser.add_argument(
        "repo_identifier",
        help="Local repo name or remote repo url"
    )
    parser.add_argument(
        "bignum",
        type=int,
        nargs="?",
        default=100000,
        help="Minimum number of files in catalog (default: 100000)"
    )
    parser.add_argument(
        "bigmb",
        type=int,
        nargs="?",
        default=50,
        help="Minimum size in MB (default: 50)"
    )
    
    args = parser.parse_args()
    
    repo_identifier = args.repo_identifier
    bignum = args.bignum
    bigmb = args.bigmb

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
