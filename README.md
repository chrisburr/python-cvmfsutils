# CernVM-FS Python Utilities

The CernVM-FS python package allows for the inspection of CernVM-FS
repositories using python. In particular to browse their file catalog
hierarchy, inspect CernVM-FS repository manifests (a.k.a. .cvmfspublished
files) and the history of named snapshots inside any CernVM-FS repository.

The support for this package is low: best effort, and with very
limited testing.

## Example Usage

```python
import cvmfs

repo = cvmfs.open_repository('http://cvmfs.fnal.gov/cvmfs/grid.cern.ch')
print('Last Revision:', repo.manifest.revision, repo.manifest.last_modified)
root_catalog = repo.retrieve_catalog(repo.manifest.root_catalog)
print('Catalog Schema:', root_catalog.schema)
for nested_catalog_ref in root_catalog.list_nested():
    print('Nested Catalog at:', nested_catalog_ref.root_path)
print('Listing repository')
for full_path, dirent in repo:
    print(full_path)
```

## Utilities

Example programs "big_catalogs" and "catdirusage" are supplied in the
"utils" directory, which are also useful for figuring out where to
split up the catalogs in a cvmfs repository. Also, "cvmfs_search" is
useful as a way to find out the original path(s) that correspond to a
cvmfs hash.

## Installation

Rpms are available in the cvmfs-contrib yum repositories for EL6 & 7.
See https://cvmfs-contrib.github.io for instructions to enable one
of those repositories. Then to install simply do:

```bash
yum install -y python-cvmfsutils
```

## Testing

The full test suite can be run by this command in the cvmfs subdirectory:

```bash
python3 test
```

The signature verification tests fail by default on EL9 because sha1 is
disallowed there for certificate checks. That can be worked around with:

```bash
update-crypto-policies --set DEFAULT:SHA1
```