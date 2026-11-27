"""fontcatalyst otl: OpenType feature audit, wrap, connect, aalt, verify and sort."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import FontCore.core_console_styles as cs

from fontcatalyst.opentype.flow_commands import (
    cmd_aalt,
    cmd_connect,
    cmd_pipeline,
    cmd_scan,
    cmd_sort,
    cmd_verify,
    cmd_wrap,
    prepare_context,
)
from fontcatalyst.opentype.flow_context import FlowContext


def _add_globals(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "paths",
        nargs="+",
        help="Font files or directories",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Recurse into subdirectories",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without writing fonts",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Skip confirmation prompts",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="DIR",
        help="Override base directory for otl_reports output",
    )
    parser.add_argument(
        "--backup",
        action="store_true",
        help="Backup fonts to backups/ before mutating",
    )


PROG = "fontcatalyst otl"


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description="OpenType feature workflow: scan, wrap, connect, aalt, verify, sort.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  %(prog)s scan ./MyFamily -r
  %(prog)s scan ./MyFamily -r --write-report
  %(prog)s connect ./MyFamily -r --dry-run
  %(prog)s connect ./MyFamily -r --apply --backup -y
  %(prog)s wrap ./MyFamily -r --backup
  %(prog)s aalt ./MyFamily -r --apply --backup -y
  %(prog)s verify ./MyFamily -r
  %(prog)s pipeline ./MyFamily -r --backup -y
""",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    scan_p = sub.add_parser(
        "scan",
        help="Audit installed features, wrap needs, gaps, and graded recommendations",
    )
    _add_globals(scan_p)
    scan_p.add_argument(
        "--write-report",
        action="store_true",
        help="Also write family_summary.json + family_matrix.txt per directory",
    )

    wrap_p = sub.add_parser(
        "wrap",
        help="Add OTL scaffolding and enrichment (TrueType and OpenType/CFF)",
    )
    _add_globals(wrap_p)

    connect_p = sub.add_parser("connect", help="Build reconnect FEA; optionally apply")
    _add_globals(connect_p)
    connect_p.add_argument(
        "--apply",
        action="store_true",
        help="Apply generated connect FEA after review",
    )
    connect_p.add_argument(
        "--replace",
        action="store_true",
        help="Replace GSUB/GPOS before applying connect FEA",
    )
    connect_p.add_argument(
        "--include-low",
        action="store_true",
        help="Include LOW tier features (e.g. salt) in connect plan",
    )
    connect_p.add_argument(
        "--include-manual",
        action="store_true",
        help="Include MANUAL tier features (contextual) in FEA — merge apply still skips them",
    )

    sort_p = sub.add_parser("sort", help="Sort GSUB/GPOS/GDEF Coverage tables")
    _add_globals(sort_p)

    aalt_p = sub.add_parser(
        "aalt",
        help="Build aalt feature referencing installed GSUB features",
    )
    _add_globals(aalt_p)
    aalt_p.add_argument(
        "--apply",
        action="store_true",
        help="Apply generated aalt FEA to fonts",
    )
    aalt_p.add_argument(
        "--force",
        action="store_true",
        help="Replace existing populated aalt",
    )

    verify_p = sub.add_parser(
        "verify",
        help="Read-only post-workflow health check",
    )
    _add_globals(verify_p)
    verify_p.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    pipe_p = sub.add_parser(
        "pipeline",
        help="scan → wrap → connect → aalt → verify → sort",
    )
    _add_globals(pipe_p)
    pipe_p.add_argument("--no-wrap", action="store_true", help="Skip wrap step")
    pipe_p.add_argument("--no-connect", action="store_true", help="Skip connect step")
    pipe_p.add_argument("--no-aalt", action="store_true", help="Skip aalt step")
    pipe_p.add_argument("--no-verify", action="store_true", help="Skip verify step")
    pipe_p.add_argument("--no-sort", action="store_true", help="Skip sort step")
    pipe_p.add_argument(
        "--include-low",
        action="store_true",
        help="Pass --include-low to connect step",
    )
    pipe_p.add_argument(
        "--include-manual",
        action="store_true",
        help="Pass --include-manual to connect step",
    )

    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    ctx = FlowContext(
        paths=args.paths,
        recursive=args.recursive,
        dry_run=args.dry_run,
        verbose=args.verbose,
        yes=args.yes,
        output_dir=args.output_dir,
        backup=args.backup,
        connect_include_low=getattr(args, "include_low", False),
        connect_include_manual=getattr(args, "include_manual", False),
        aalt_force=getattr(args, "force", False),
    )

    if prepare_context(ctx) != 0:
        return 1

    command = args.command
    if command == "scan":
        return cmd_scan(ctx, write_report=args.write_report)
    if command == "wrap":
        return cmd_wrap(ctx)
    if command == "connect":
        return cmd_connect(ctx, apply=args.apply, replace=args.replace)
    if command == "sort":
        return cmd_sort(ctx)
    if command == "aalt":
        return cmd_aalt(ctx, apply=args.apply)
    if command == "verify":
        return cmd_verify(ctx, strict=args.strict)
    if command == "pipeline":
        return cmd_pipeline(
            ctx,
            no_wrap=args.no_wrap,
            no_connect=args.no_connect,
            no_aalt=args.no_aalt,
            no_verify=args.no_verify,
            no_sort=args.no_sort,
        )

    cs.StatusIndicator("error").add_message(f"Unknown command: {command}").emit()
    return 1

