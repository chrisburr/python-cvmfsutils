# Building python-cvmfsutils

## Development Setup

This project uses [pixi](https://pixi.sh) for environment management:

```bash
# Install dependencies
pixi install

# Run tests
pixi run test

# Generate RPM spec file
pixi run generate-spec
```

## Version Management

The project uses `setuptools-scm` for automatic version management from git tags. The version is automatically determined from:

1. Git tags (for releases)
2. Git commit hash and distance from last tag (for development versions)

## RPM Packaging

### Automatic Spec File Generation

The RPM spec file is generated automatically to avoid the need for external macros in the OpenSUSE Build System (OBS):

- **Template**: `rpm/python-cvmfsutils.spec.in` contains placeholders for version
- **Generator**: `generate_spec.py` reads the template and substitutes the current version from setuptools-scm
- **Output**: `rpm/python-cvmfsutils.spec` contains the final spec file with embedded version

To generate the spec file manually:

```bash
python generate_spec.py
# or using pixi:
pixi run generate-spec
```

### CI/CD Integration

The GitHub Actions workflows automatically:

1. Generate the spec file with the correct version
2. Build RPMs for AlmaLinux 8/9 and openSUSE Leap/Tumbleweed
3. Test installation and functionality
4. Verify version consistency between setuptools-scm and the spec file

### OpenSUSE Build System (OBS) Compatibility

The generated spec file is designed to work with OBS without requiring external macros:

- No `%{version}` macro usage - version is embedded directly
- Single source for version information via setuptools-scm
- Template-based generation ensures consistency

## Package Structure

- **Source layout**: Code is in `src/cvmfs/` following modern Python packaging standards
- **Console scripts**: Utilities are defined as entry points in `setup.cfg`
- **Dependencies**: Declared in `setup.cfg` with appropriate version constraints

## Testing

CI tests across multiple platforms:

- **Python versions**: 3.8-3.12
- **Operating systems**: Ubuntu, macOS (Intel/ARM)
- **RPM builds**: AlmaLinux 8/9, openSUSE Leap 15.5/15.6, openSUSE Tumbleweed

Local testing:

```bash
# Run test suite
pixi run test

# Test RPM spec generation
pixi run generate-spec
```