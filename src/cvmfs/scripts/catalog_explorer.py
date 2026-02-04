#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVMFS Catalog Explorer CLI

Explore the contents of CVMFS catalogs to understand what makes them large.
"""

import argparse
import sys
from collections import defaultdict

import cvmfs


def _format_bytes(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    if bytes_val == 0:
        return "0 B"
    suffixes = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(bytes_val)
    while val >= 1024 and i < len(suffixes) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f} {suffixes[i]}"


def _format_count(count: int) -> str:
    """Format large numbers with K/M suffixes."""
    if count < 1000:
        return str(count)
    elif count < 1_000_000:
        return f"{count/1000:.1f}K"
    else:
        return f"{count/1_000_000:.1f}M"


def cmd_ls(repo, revision, path: str, long_format: bool = False):
    """List directory contents."""
    entries = list(revision.list_directory(path))
    if not entries:
        print(f"No entries found at {path}", file=sys.stderr)
        return

    # Sort: directories first, then by name
    entries.sort(key=lambda e: (not e.is_directory(), e.name.lower()))

    for entry in entries:
        if entry.is_directory():
            type_char = "d"
            size_str = "-"
            suffix = "/"
            if entry.is_nested_catalog_mountpoint():
                suffix = "/ [catalog]"
        elif entry.is_symlink():
            type_char = "l"
            size_str = "-"
            suffix = f" -> {entry.symlink}"
        else:
            type_char = "-"
            size_str = _format_bytes(entry.size)
            suffix = ""

        if long_format:
            print(f"{type_char} {size_str:>10}  {entry.name}{suffix}")
        else:
            print(f"{entry.name}{suffix}")


def cmd_stat(repo, revision, path: str):
    """Show statistics for a path and its catalog."""
    # Look up the entry
    entry = revision.lookup(path)
    if not entry:
        print(f"Path not found: {path}", file=sys.stderr)
        return

    print(f"Path: {path}")
    print()

    # Entry info
    print("Entry Information:")
    if entry.is_directory():
        print(f"  Type: directory")
        if entry.is_nested_catalog_mountpoint():
            print(f"  Note: This is a nested catalog mountpoint")
    elif entry.is_symlink():
        print(f"  Type: symlink -> {entry.symlink}")
    else:
        print(f"  Type: file")
        print(f"  Size: {_format_bytes(entry.size)}")
        if entry.content_hash:
            print(f"  Hash: {entry.content_hash_string()}")

    print()

    # Catalog info
    catalog = revision.retrieve_catalog_for_path(path)
    print("Catalog Information:")
    print(f"  Catalog path: {catalog.root_prefix or '/'}")
    print(f"  Database size: {_format_bytes(catalog.db_size())}")

    # Count entries in catalog
    entry_count = 0
    for _ in catalog:
        entry_count += 1
    print(f"  Total entries: {_format_count(entry_count)}")

    # List nested catalogs
    nested = list(catalog.list_nested())
    if nested:
        print(f"  Nested catalogs: {len(nested)}")


def cmd_du(repo, revision, path: str, depth: int = None, expand_threshold: float = 0.2,
            max_lines: int = 30):
    """Show disk usage (entry counts) for subdirectories.

    If depth is None, uses adaptive expansion: recursively expands any
    subdirectory containing more than expand_threshold (default 20%) of
    its parent's files, up to max_lines output lines.
    """
    catalog = revision.retrieve_catalog_for_path(path)

    # Normalize path
    if path == "/":
        path = ""
    path = path.rstrip("/")
    pathlen = len(path)

    # Build a tree of all entries with their full paths
    all_entries = []
    for entry_path, entry in catalog:
        # Skip entries not under our path
        if not entry_path.startswith(path + "/") and entry_path != path:
            continue
        rel = entry_path[pathlen:].lstrip("/")
        if not rel:
            continue
        all_entries.append((entry_path, entry))

    if not all_entries:
        print(f"No entries found under {path or '/'}", file=sys.stderr)
        return

    def count_at_depth(entries, base_path, target_depth):
        """Count files/dirs/size for immediate children at target_depth."""
        counts = defaultdict(lambda: {"files": 0, "dirs": 0, "size": 0})
        base_len = len(base_path)

        for entry_path, entry in entries:
            if not entry_path.startswith(base_path + "/"):
                continue
            rel = entry_path[base_len:].lstrip("/")
            if not rel:
                continue

            parts = rel.split("/")
            if len(parts) > target_depth:
                subdir = "/".join(parts[:target_depth])
            else:
                subdir = rel

            full_subdir = f"{base_path}/{subdir}" if base_path else f"/{subdir}"

            if entry.is_directory():
                counts[full_subdir]["dirs"] += 1
            else:
                counts[full_subdir]["files"] += 1
                counts[full_subdir]["size"] += entry.size

        return counts

    def get_display_paths(entries, base_path, expand_thresh, max_depth=5):
        """Recursively determine which paths to display.

        Expands directories that have > expand_thresh of parent's files.
        Returns dict of {path: stats} for paths to display.
        """
        result = {}

        # Get counts at depth 1 from base_path
        counts = count_at_depth(entries, base_path, 1)
        if not counts:
            return result

        total_files = sum(c["files"] for c in counts.values())
        if total_files == 0:
            # No files, just show directories
            for subdir, stats in counts.items():
                result[subdir] = stats
            return result

        for subdir, stats in counts.items():
            file_ratio = stats["files"] / total_files if total_files > 0 else 0

            # Calculate depth relative to original path
            rel_depth = subdir.count("/") - (path.count("/") if path else 0)

            # Only expand if: >threshold, within depth limit, has multiple files
            if (file_ratio > expand_thresh and
                rel_depth < max_depth and
                stats["files"] > 100):  # Only expand if substantial
                # Expand this directory - recurse into it
                sub_results = get_display_paths(entries, subdir, expand_thresh, max_depth)
                if sub_results:
                    result.update(sub_results)
                else:
                    # No children to show, show this directory
                    result[subdir] = stats
            else:
                # Don't expand, show this directory
                result[subdir] = stats

        return result

    # Get paths to display
    if depth is not None:
        # Fixed depth mode
        display = count_at_depth(all_entries, path, depth)
    else:
        # Adaptive mode
        display = get_display_paths(all_entries, path, expand_threshold)

    if not display:
        print(f"No entries found under {path or '/'}", file=sys.stderr)
        return

    # Sort by file count (largest first)
    sorted_dirs = sorted(display.items(), key=lambda x: x[1]["files"], reverse=True)

    # Check which paths are nested catalog mountpoints
    nested_paths = {ref.root_path for ref in catalog.list_nested()}

    print(f"{'Files':>10} {'Dirs':>8} {'Size':>10}  Path")
    print("-" * 60)

    # Limit output and collapse small entries into "other"
    shown = 0
    other_stats = {"files": 0, "dirs": 0, "size": 0}
    other_count = 0

    for subdir, stats in sorted_dirs:
        if shown < max_lines:
            marker = " [catalog]" if subdir in nested_paths else ""
            print(
                f"{_format_count(stats['files']):>10} "
                f"{_format_count(stats['dirs']):>8} "
                f"{_format_bytes(stats['size']):>10}  "
                f"{subdir}{marker}"
            )
            shown += 1
        else:
            other_stats["files"] += stats["files"]
            other_stats["dirs"] += stats["dirs"]
            other_stats["size"] += stats["size"]
            other_count += 1

    if other_count > 0:
        print(
            f"{_format_count(other_stats['files']):>10} "
            f"{_format_count(other_stats['dirs']):>8} "
            f"{_format_bytes(other_stats['size']):>10}  "
            f"... and {other_count} more"
        )

    # Summary
    total_files = sum(s["files"] for s in display.values())
    total_dirs = sum(s["dirs"] for s in display.values())
    total_size = sum(s["size"] for s in display.values())
    print("-" * 60)
    print(
        f"{_format_count(total_files):>10} "
        f"{_format_count(total_dirs):>8} "
        f"{_format_bytes(total_size):>10}  "
        f"TOTAL"
    )


def cmd_tree(repo, revision, path: str, max_depth: int = 2):
    """Show tree of nested catalogs."""
    catalog = revision.retrieve_catalog_for_path(path)

    def print_catalog(cat, indent=0):
        prefix = "  " * indent
        size = _format_bytes(cat.db_size())

        # Count entries
        entry_count = sum(1 for _ in cat)

        print(f"{prefix}{cat.root_prefix or '/'} ({size}, {_format_count(entry_count)} entries)")

        if indent >= max_depth:
            nested = list(cat.list_nested())
            if nested:
                print(f"{prefix}  ... {len(nested)} nested catalogs")
            return

        for ref in cat.list_nested():
            try:
                child_cat = ref.retrieve_from(repo)
                print_catalog(child_cat, indent + 1)
            except Exception as e:
                print(f"{prefix}  {ref.root_path} (failed to load: {e})")

    print_catalog(catalog)


def main():
    parser = argparse.ArgumentParser(
        description="Explore CVMFS catalog contents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  ls      List directory contents
  stat    Show statistics for a path and its catalog
  du      Show entry counts per subdirectory (adaptive depth by default)
  tree    Show tree of nested catalogs

Examples:
  # List root directory
  catalog_explorer http://cvmfs-stratum-one.cern.ch/cvmfs/lhcb.cern.ch ls /

  # Show detailed listing
  catalog_explorer lhcb.cern.ch ls -l /lib

  # Show why a catalog is large (auto-expands heavy directories)
  catalog_explorer lhcb.cern.ch du /conda

  # Show at fixed depth
  catalog_explorer lhcb.cern.ch du /conda -d 2

  # Show nested catalog tree
  catalog_explorer lhcb.cern.ch tree /
""",
    )

    parser.add_argument(
        "repo_identifier",
        help="Repository URL or name",
    )

    parser.add_argument(
        "command",
        choices=["ls", "stat", "du", "tree"],
        help="Command to run",
    )

    parser.add_argument(
        "path",
        nargs="?",
        default="/",
        help="Path to explore (default: /)",
    )

    parser.add_argument(
        "-l", "--long",
        action="store_true",
        help="Long format for ls",
    )

    parser.add_argument(
        "-d", "--depth",
        type=int,
        default=None,
        help="Depth for du/tree commands (default: adaptive for du, 2 for tree)",
    )

    parser.add_argument(
        "--cache-dir",
        default=None,
        help="Cache directory for downloaded catalogs",
    )

    args = parser.parse_args()

    # Open repository
    try:
        repo = cvmfs.open_repository(args.repo_identifier, cache_dir=args.cache_dir)
    except Exception as e:
        print(f"Error opening repository: {e}", file=sys.stderr)
        sys.exit(1)

    revision = repo.get_current_revision()

    # Normalize path
    path = args.path
    if not path.startswith("/"):
        path = "/" + path

    # Run command
    if args.command == "ls":
        cmd_ls(repo, revision, path, long_format=args.long)
    elif args.command == "stat":
        cmd_stat(repo, revision, path)
    elif args.command == "du":
        cmd_du(repo, revision, path, depth=args.depth)
    elif args.command == "tree":
        cmd_tree(repo, revision, path, max_depth=args.depth if args.depth is not None else 2)


if __name__ == "__main__":
    main()
