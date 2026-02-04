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

### catalog_visualizer

Generate an interactive HTML visualization of the catalog hierarchy:

```bash
catalog_visualizer http://cvmfs-stratum-one.cern.ch/cvmfs/lhcb.cern.ch
catalog_visualizer lhcb.cern.ch --stop-threshold 5MB  # Stop at large catalogs
catalog_visualizer lhcb.cern.ch -j 8                  # Parallel downloads
```

### catalog_explorer

Explore catalog contents to understand why catalogs are large:

```bash
catalog_explorer lhcb.cern.ch ls /lib           # List directory
catalog_explorer lhcb.cern.ch ls -l /lib        # Long format with sizes
catalog_explorer lhcb.cern.ch stat /conda       # Show catalog statistics
catalog_explorer lhcb.cern.ch du /conda         # Find where files are (adaptive)
catalog_explorer lhcb.cern.ch du /conda -d 2    # Fixed depth
catalog_explorer lhcb.cern.ch tree /            # Show nested catalog tree
```

### Other utilities

- `big_catalogs` - List large catalogs by file count or size
- `catdirusage` - Count files in subdirectories
- `cvmfs_search` - Find paths for a given content hash

## Installation

Rpms are available in the cvmfs-contrib yum repositories for current versions of Enterprise Linux.
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
