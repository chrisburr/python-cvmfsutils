#!/usr/bin/env python3
"""
Generate python-cvmfsutils.spec from template.

This script generates the RPM spec file for OpenSUSE Build Service.
The version is extracted from the first changelog entry in the template,
making the changelog the single source of truth for the release version.

The generated spec file is checked into git so OBS can read it directly.
"""

import re
import stat
import sys
from pathlib import Path


def extract_version_from_changelog(template_content):
    """Extract version from the first changelog entry.

    Changelog entries look like:
        * Wed Aug 13 2025 Chris Burr <...> - 0.6.0-1

    Commented entries (starting with #) are skipped.

    Returns the version (e.g., "0.6.0").
    """
    # Find the %changelog section and the first non-commented entry
    changelog_match = re.search(
        r"%changelog\s*\n(?:#[^\n]*\n)*\*.*-\s*(\d+\.\d+\.?\d*)-\d+",
        template_content,
    )
    if not changelog_match:
        return None
    return changelog_match.group(1)


def main():
    """Generate spec file from template."""

    # Read template
    template_path = Path("rpm/python-cvmfsutils.spec.in")
    if not template_path.exists():
        print(f"Template file not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    template_content = template_path.read_text()

    # Extract version from changelog
    version = extract_version_from_changelog(template_content)
    if not version:
        print("Error: Could not extract version from changelog", file=sys.stderr)
        print("Ensure the first changelog entry has format: * DATE NAME - VERSION-RELEASE", file=sys.stderr)
        sys.exit(1)

    # Replace version placeholder
    spec_content = template_content.replace("@VERSION@", version)

    # Write generated spec file
    output_path = Path("rpm/python-cvmfsutils.spec")

    # Remove existing file if it exists (may be read-only)
    if output_path.exists():
        output_path.chmod(stat.S_IWUSR | stat.S_IRUSR)
        output_path.unlink()

    output_path.write_text(spec_content)

    # Make the file read-only to discourage direct edits
    output_path.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)

    print(f"Generated {output_path} with version {version}")


if __name__ == "__main__":
    main()
