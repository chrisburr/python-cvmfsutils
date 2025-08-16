#!/usr/bin/env python3
"""
Generate python-cvmfsutils.spec from template using setuptools_scm version.

This script ensures the RPM spec file has the correct version for OpenSUSE Build System
without requiring external macros to be passed in.
"""

import sys
from pathlib import Path
from setuptools_scm import get_version


def main():
    """Generate spec file from template."""
    
    # Get version from setuptools_scm
    try:
        version = get_version()
    except Exception as e:
        print(f"Error getting version from setuptools_scm: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Read template
    template_path = Path("rpm/python-cvmfsutils.spec.in")
    if not template_path.exists():
        print(f"Template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)
    
    template_content = template_path.read_text()
    
    # Replace version placeholder
    spec_content = template_content.replace("@VERSION@", version)
    
    # Write generated spec file
    output_path = Path("rpm/python-cvmfsutils.spec")
    output_path.write_text(spec_content)
    
    print(f"Generated {output_path} with version {version}")


if __name__ == "__main__":
    main()