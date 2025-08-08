#!/usr/bin/env python3

import argparse
import cvmfs
import os


def main():
    parser = argparse.ArgumentParser(
        description="Prints the number of files in the current catalog for each sub-directory under topdir, sorted smallest to largest."
    )
    parser.add_argument(
        "repo_identifier",
        help="Local repo name or remote repo url"
    )
    parser.add_argument(
        "topdir",
        help="Top directory to analyze"
    )
    
    args = parser.parse_args()
    
    repo_identifier = args.repo_identifier
    toppath = args.topdir

    repo = cvmfs.open_repository(repo_identifier)
    revision = repo.get_current_revision()
    clg = revision.retrieve_catalog_for_path(toppath)
    counts = {}
    pathlen = len(toppath)
    for dirent in clg:
        file = dirent[0]
        if len(file) <= pathlen:
            continue
        if file[0:pathlen] != toppath:
            continue
        slash = file.find('/', pathlen+1)
        if slash == -1:
            counts[file] = 0
        else:
            counts[file[0:slash]] += 1
    for dir in sorted(counts, key=counts.get):
        if counts[dir] > 0:
            print(str(counts[dir]) + '\t' + dir)


if __name__ == "__main__":
    main()
