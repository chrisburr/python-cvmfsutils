#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVMFS Catalog Visualizer CLI

Generate interactive visualizations of CVMFS catalog hierarchy and download costs.
"""

import argparse
import json
import sys
import webbrowser
from pathlib import Path

import cvmfs
from cvmfs.visualizer import CatalogTreeBuilder, generate_html


def parse_size(size_str: str) -> int:
    """Parse a size string like '2MB' or '500KB' into bytes."""
    size_str = size_str.strip().upper()

    multipliers = {
        "B": 1,
        "KB": 1024,
        "K": 1024,
        "MB": 1024 * 1024,
        "M": 1024 * 1024,
        "GB": 1024 * 1024 * 1024,
        "G": 1024 * 1024 * 1024,
    }

    for suffix, mult in sorted(multipliers.items(), key=lambda x: -len(x[0])):
        if size_str.endswith(suffix):
            num_str = size_str[: -len(suffix)].strip()
            try:
                return int(float(num_str) * mult)
            except ValueError:
                raise argparse.ArgumentTypeError(
                    f"Invalid size value: {size_str}"
                )

    # No suffix, assume bytes
    try:
        return int(size_str)
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size value: {size_str}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate interactive visualization of CVMFS catalog hierarchy",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate HTML visualization (opens in browser)
  catalog_visualizer http://cvmfs-stratum-one.cern.ch/cvmfs/lhcb.cern.ch

  # Stop descending at 5MB catalogs
  catalog_visualizer lhcb.cern.ch --stop-threshold 5MB

  # Limit depth
  catalog_visualizer lhcb.cern.ch --max-depth 5

  # Output JSON for debugging
  catalog_visualizer lhcb.cern.ch --json

  # Save to specific file
  catalog_visualizer lhcb.cern.ch -o my_visualization.html
""",
    )

    parser.add_argument(
        "repo_identifier", help="Repository URL or local path"
    )

    parser.add_argument(
        "-s",
        "--stop-threshold",
        type=parse_size,
        default="2MB",
        metavar="SIZE",
        help="Stop descending when catalog exceeds this size (default: 2MB). "
        "Accepts suffixes: B, KB, MB, GB",
    )

    parser.add_argument(
        "-d",
        "--max-depth",
        type=int,
        default=None,
        metavar="N",
        help="Maximum depth to traverse (default: unlimited)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON data instead of HTML",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        metavar="FILE",
        help="Output file path (default: <repo_name>_catalogs.html)",
    )

    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser after generating HTML",
    )

    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    args = parser.parse_args()

    # Open repository
    if not args.quiet:
        print(f"Opening repository: {args.repo_identifier}", file=sys.stderr)

    try:
        repo = cvmfs.open_repository(args.repo_identifier)
    except Exception as e:
        print(f"Error opening repository: {e}", file=sys.stderr)
        sys.exit(1)

    repo_name = repo.fqrn

    # Build catalog tree
    if not args.quiet:
        print("Building catalog tree...", file=sys.stderr)
        if args.stop_threshold:
            print(
                f"  Stop threshold: {args.stop_threshold / (1024*1024):.1f} MB",
                file=sys.stderr,
            )
        if args.max_depth:
            print(f"  Max depth: {args.max_depth}", file=sys.stderr)

    builder = CatalogTreeBuilder(
        repo,
        stop_threshold=args.stop_threshold,
        max_depth=args.max_depth,
    )

    try:
        root_node = builder.build()
    except Exception as e:
        print(f"Error building catalog tree: {e}", file=sys.stderr)
        sys.exit(1)

    if not args.quiet:
        print(
            f"Downloaded {builder.catalogs_downloaded} catalogs "
            f"({builder.total_bytes_downloaded / (1024*1024):.2f} MB)",
            file=sys.stderr,
        )

    # Output JSON
    if args.json:
        output = json.dumps(root_node.to_dict(), indent=2)
        if args.output:
            args.output.write_text(output)
            if not args.quiet:
                print(f"JSON written to: {args.output}", file=sys.stderr)
        else:
            print(output)
        return

    # Generate HTML
    html = generate_html(
        root_node,
        repo_name,
        catalogs_downloaded=builder.catalogs_downloaded,
        total_downloaded=builder.total_bytes_downloaded,
    )

    # Determine output path
    if args.output:
        output_path = args.output
    else:
        safe_name = repo_name.replace("/", "_").replace(".", "_")
        output_path = Path(f"{safe_name}_catalogs.html")

    output_path.write_text(html)

    if not args.quiet:
        print(f"Visualization written to: {output_path}", file=sys.stderr)

    # Open browser
    if not args.no_browser:
        webbrowser.open(f"file://{output_path.absolute()}")


if __name__ == "__main__":
    main()
