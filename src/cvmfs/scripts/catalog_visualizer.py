#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CVMFS Catalog Visualizer CLI

Generate interactive visualizations of CVMFS catalog hierarchy and download costs.
"""

import argparse
import json
import resource
import shutil
import sys
import webbrowser
from pathlib import Path

import cvmfs
from cvmfs.visualizer import CatalogTreeBuilder, generate_html


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


class ProgressReporter:
    """Reports build progress to stderr with live updates."""

    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self.is_tty = sys.stderr.isatty()
        self.term_width = shutil.get_terminal_size().columns
        self._last_line_len = 0

    def __call__(self, progress: dict) -> None:
        if self.quiet:
            return

        path = progress["path"]
        downloaded = progress["catalogs_downloaded"]
        found = progress["catalogs_found"]
        large = progress["large_catalogs_found"]
        bytes_dl = progress["bytes_downloaded"]
        bytes_skip = progress["bytes_skipped"]
        cache_hits = progress.get("cache_hits", 0)
        bytes_cache = progress.get("bytes_from_cache", 0)

        # Calculate network bytes (total minus cached)
        bytes_net = bytes_dl - bytes_cache
        net_count = downloaded - cache_hits

        # Truncate path if needed
        max_path_len = min(40, self.term_width - 60)
        if len(path) > max_path_len:
            path = "..." + path[-(max_path_len - 3) :]

        status = (
            f"  {downloaded}/{found} catalogs, {large} large | "
            f"{_format_bytes(bytes_net)} ({net_count}) net, "
            f"{_format_bytes(bytes_cache)} ({cache_hits}) cached, "
            f"{_format_bytes(bytes_skip)} skipped | {path}"
        )

        if self.is_tty:
            # Clear previous line and print new status
            clear = "\r" + " " * self._last_line_len + "\r"
            sys.stderr.write(clear + status)
            sys.stderr.flush()
            self._last_line_len = len(status)
        # Non-TTY: don't spam, just update occasionally handled by caller

    def finish(self) -> None:
        """Clear the progress line."""
        if not self.quiet and self.is_tty:
            sys.stderr.write("\r" + " " * self._last_line_len + "\r")
            sys.stderr.flush()


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


def _increase_file_limit() -> None:
    """Increase the open file descriptor limit to avoid 'Too many open files' errors.

    On macOS, the default soft limit is often 256, which is insufficient when
    traversing large CVMFS repositories with many nested catalogs.
    """
    try:
        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        # Increase soft limit to hard limit (or a reasonable maximum)
        new_soft = min(hard, 10240)
        if new_soft > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new_soft, hard))
    except (ValueError, OSError):
        # Silently ignore if we can't change the limit
        pass


def main():
    _increase_file_limit()

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

  # Use custom cache directory
  catalog_visualizer lhcb.cern.ch --cache-dir /path/to/cache

  # Disable caching
  catalog_visualizer lhcb.cern.ch --no-cache

  # Ignore specific paths
  catalog_visualizer lhcb.cern.ch --ignore /lib/var --ignore /lib/tmp
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

    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path("~/.cache/cvmfs").expanduser(),
        metavar="DIR",
        help="Directory for caching downloaded catalogs (default: ~/.cache/cvmfs)",
    )

    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable disk caching of downloaded catalogs",
    )

    parser.add_argument(
        "--ignore",
        action="append",
        default=[],
        metavar="PATH",
        help="Ignore paths matching this prefix (can be specified multiple times)",
    )

    parser.add_argument(
        "-j",
        "--workers",
        type=int,
        default=4,
        metavar="N",
        help="Number of parallel workers for downloading catalogs (default: 4)",
    )

    args = parser.parse_args()

    # Determine cache directory
    cache_dir = None if args.no_cache else str(args.cache_dir)

    # Create cache directory if it doesn't exist
    if cache_dir:
        Path(cache_dir).mkdir(parents=True, exist_ok=True)

    # Open repository
    if not args.quiet:
        print(f"Opening repository: {args.repo_identifier}", file=sys.stderr)
        if cache_dir:
            print(f"Using cache directory: {cache_dir}", file=sys.stderr)

    try:
        repo = cvmfs.open_repository(args.repo_identifier, cache_dir=cache_dir)
    except Exception as e:
        print(f"Error opening repository: {e}", file=sys.stderr)
        sys.exit(1)

    repo_name = repo.fqrn

    # Normalize ignore paths (ensure they start with /)
    ignore_paths = []
    for path in args.ignore:
        if not path.startswith("/"):
            path = "/" + path
        ignore_paths.append(path)

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
        if ignore_paths:
            print(f"  Ignoring: {', '.join(ignore_paths)}", file=sys.stderr)

    progress = ProgressReporter(quiet=args.quiet)

    builder = CatalogTreeBuilder(
        repo,
        stop_threshold=args.stop_threshold,
        max_depth=args.max_depth,
        ignore_paths=ignore_paths,
        progress_callback=progress,
        max_workers=args.workers,
    )

    try:
        root_node = builder.build()
    except Exception as e:
        progress.finish()
        print(f"Error building catalog tree: {e}", file=sys.stderr)
        sys.exit(1)

    progress.finish()

    if not args.quiet:
        ignored_msg = ""
        if builder.ignored_count > 0:
            ignored_msg = f", {builder.ignored_count} ignored"
        print(
            f"Found {builder.catalogs_found} catalogs "
            f"({builder.large_catalogs_found} large, exploration stopped{ignored_msg})",
            file=sys.stderr,
        )
        net_count = builder.catalogs_downloaded - builder.cache_hits
        net_bytes = builder.total_bytes_downloaded - builder.bytes_from_cache
        print(
            f"Processed {builder.catalogs_downloaded} catalogs: "
            f"{net_count} from network ({_format_bytes(net_bytes)}), "
            f"{builder.cache_hits} from cache ({_format_bytes(builder.bytes_from_cache)}), "
            f"skipped {_format_bytes(builder.bytes_skipped)}",
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
        repo_url=args.repo_identifier,
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
