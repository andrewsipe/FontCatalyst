"""fontcatalyst features: OpenType feature audit, wrap, connect, aalt, verify and sort."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import FontCore.core_console_styles as cs
from FontCore.core_cli_help import (
    RichHelp,
    docs_section,
    examples_section,
    exit_status_section,
    notes_section,
    safety_panel,
)

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


DOCS_HINT = "https://andrewsipe.github.io/FontCatalyst/"

EXIT_CODES = {
    "0": "finished (individual files may still be reported as warnings or errors)",
    "1": "no fonts found, or the run was cancelled",
}

# command -> (panel text, panel rows, examples, notes)
HELP = {
    "scan": (
        "Read-only audit. Reports which GSUB and GPOS features each font has, what its glyphs could use, "
        "and graded recommendations. Fonts are not changed.",
        (("Fonts changed", "never"), ("Write the family files", "--write-report")),
        [("fontcatalyst features scan fonts/ -r", "audit a family"),
         ("fontcatalyst features scan fonts/ -r --write-report", "also write family_summary.json and family_matrix.txt")],
        ["--write-report puts the files in an otl_reports folder beside the fonts, or under --report-dir."],
    ),
    "wrap": (
        "Edits fonts in place. Adds the missing OpenType scaffolding (script, language and feature records) "
        "to TrueType and CFF fonts.",
        (("Preview only", "--dry-run"), ("Keep the originals", "--backup")),
        [("fontcatalyst features wrap fonts/ -r --dry-run", "show what would change"),
         ("fontcatalyst features wrap fonts/ -r --backup", "back up to backups/, then wrap")],
        ["Nothing is written with --dry-run."],
    ),
    "connect": (
        "Builds the feature code that would reconnect features to their glyphs. Fonts change only with --apply.",
        (("Preview", "default (writes the .fea only)"), ("Write into fonts", "--apply"), ("Keep the originals", "--backup")),
        [("fontcatalyst features connect fonts/ -r --dry-run", "see the plan"),
         ("fontcatalyst features connect fonts/ -r --apply --backup -y", "apply it, backing up first")],
        ["--replace swaps out GSUB and GPOS before applying. Use it only when the existing tables are wrong.",
         "--include-low adds low-tier features such as salt. --include-manual adds contextual ones to the .fea, but apply still skips them."],
    ),
    "sort": (
        "Edits fonts in place. Sorts the GSUB, GPOS and GDEF Coverage tables and the arrays that follow them. "
        "Fonts that are already in order are left alone.",
        (("Preview only", "--dry-run"), ("Keep the originals", "--backup")),
        [("fontcatalyst features sort fonts/ -r --dry-run", "list the fonts that need it"),
         ("fontcatalyst features sort fonts/ -r --backup -y", "sort them, backing up first")],
        ["`fontcatalyst PATH --repair` applies the same sort as part of its structural repair."],
    ),
    "aalt": (
        "Builds an aalt feature that references the installed GSUB features. Fonts change only with --apply.",
        (("Preview", "default"), ("Write into fonts", "--apply"), ("Replace a filled aalt", "--force")),
        [("fontcatalyst features aalt fonts/ -r --apply --backup -y", "add aalt to every font")],
        ["A font that already has a populated aalt is skipped unless you pass --force."],
    ),
    "verify": (
        "Read-only health check for after the other steps. Fonts are not changed.",
        (("Fonts changed", "never"), ("Warnings as errors", "--strict")),
        [("fontcatalyst features verify fonts/ -r", "check a family"),
         ("fontcatalyst features verify fonts/ -r --strict", "fail on warnings too")],
        [],
    ),
    "pipeline": (
        "Runs scan, wrap, connect, aalt, verify and sort in order, editing fonts in place.",
        (("Preview", "--dry-run"), ("Keep the originals", "--backup"), ("Leave a step out", "--no-wrap, --no-connect, --no-aalt, --no-verify, --no-sort")),
        [("fontcatalyst features pipeline fonts/ -r --backup -y", "the whole workflow")],
        ["--include-low and --include-manual go to the connect step."],
    ),
}


def _command_help(command: str) -> dict:
    panel, rows, examples, notes = HELP[command]
    return dict(
        action=RichHelp,
        console=cs.get_console(),
        help="show this help message and exit",
        panel=safety_panel(panel, rows),
        inline=None,
        footer=[
            examples_section(examples),
            *([notes_section(notes)] if notes else []),
            exit_status_section(EXIT_CODES),
            docs_section(DOCS_HINT),
        ],
    )


def _add_globals(parser: argparse.ArgumentParser, command: str) -> None:
    """The shared options, in the same groups as the other commands. Group creation order is display order."""
    g_in = parser.add_argument_group("input")
    g_cmd = parser.add_argument_group(f"{command} options") if command not in ("sort", "wrap") else None
    g_run = parser.add_argument_group("run")
    g_out = parser.add_argument_group("output")
    g_gen = parser.add_argument_group("general")
    g_in.add_argument("paths", nargs="+", metavar="PATH", help="font files or directories")
    g_in.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    g_run.add_argument("-n", "--dry-run", action="store_true", help="preview changes without writing fonts")
    g_run.add_argument("-y", "--yes", action="store_true", help="skip confirmation prompts")
    g_run.add_argument("-v", "--verbose", action="store_true", help="verbose output")
    if command not in ("scan", "verify"):
        g_out.add_argument("--backup", action="store_true", help="copy fonts to backups/ before changing them")
    g_out.add_argument(
        "--report-dir", "--output-dir", dest="output_dir", type=Path, metavar="DIR",
        help="put the otl_reports folders under DIR instead of beside the fonts",
    )
    g_gen.add_argument("-h", "--help", **_command_help(command))
    parser._cmd = g_cmd


def _sub(sub, command: str, help_text: str) -> argparse.ArgumentParser:
    p = sub.add_parser(command, help=help_text, add_help=False, allow_abbrev=False,
                       prog=f"{PROG} {command}", description=HELP[command][0])
    _add_globals(p, command)
    return p


PROG = "fontcatalyst features"


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

    scan_p = _sub(sub, "scan", "Audit installed features, wrap needs, gaps, and graded recommendations")
    scan_p._cmd.add_argument(
        "--write-report",
        action="store_true",
        help="Also write family_summary.json + family_matrix.txt per directory",
    )

    wrap_p = _sub(sub, "wrap", "Add OTL scaffolding and enrichment (TrueType and OpenType/CFF)")

    connect_p = _sub(sub, "connect", "Build reconnect FEA; optionally apply")
    connect_p._cmd.add_argument(
        "--apply",
        action="store_true",
        help="Apply generated connect FEA after review",
    )
    connect_p._cmd.add_argument(
        "--replace",
        action="store_true",
        help="Replace GSUB/GPOS before applying connect FEA",
    )
    connect_p._cmd.add_argument(
        "--include-low",
        action="store_true",
        help="Include LOW tier features (e.g. salt) in connect plan",
    )
    connect_p._cmd.add_argument(
        "--include-manual",
        action="store_true",
        help="Include MANUAL tier features (contextual) in FEA — merge apply still skips them",
    )

    sort_p = _sub(sub, "sort", "Sort GSUB/GPOS/GDEF Coverage tables")

    aalt_p = _sub(sub, "aalt", "Build aalt feature referencing installed GSUB features")
    aalt_p._cmd.add_argument(
        "--apply",
        action="store_true",
        help="Apply generated aalt FEA to fonts",
    )
    aalt_p._cmd.add_argument(
        "--force",
        action="store_true",
        help="Replace existing populated aalt",
    )

    verify_p = _sub(sub, "verify", "Read-only post-workflow health check")
    verify_p._cmd.add_argument(
        "--strict",
        action="store_true",
        help="Treat warnings as errors",
    )

    pipe_p = _sub(sub, "pipeline", "scan → wrap → connect → aalt → verify → sort")
    pipe_p._cmd.add_argument("--no-wrap", action="store_true", help="Skip wrap step")
    pipe_p._cmd.add_argument("--no-connect", action="store_true", help="Skip connect step")
    pipe_p._cmd.add_argument("--no-aalt", action="store_true", help="Skip aalt step")
    pipe_p._cmd.add_argument("--no-verify", action="store_true", help="Skip verify step")
    pipe_p._cmd.add_argument("--no-sort", action="store_true", help="Skip sort step")
    pipe_p._cmd.add_argument(
        "--include-low",
        action="store_true",
        help="Pass --include-low to connect step",
    )
    pipe_p._cmd.add_argument(
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
        backup=getattr(args, "backup", False),
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

