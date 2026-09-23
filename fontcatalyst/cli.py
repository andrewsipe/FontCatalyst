"""Font Catalyst command line."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import FontCore.core_console_styles as cs
from FontCore.core_cli_help import (
    RichHelp,
    choices_section,
    docs_section,
    examples_section,
    exit_status_section,
    line_section,
    notes_section,
    safety_panel,
)
from FontCore.core_file_collector import iter_font_files

from fontcatalyst import __version__
from fontcatalyst.folders import common_parent, remove_if_empty, slots_for
from fontcatalyst.pipeline import convert_file, emit, emit_outcome, ingest_file
from fontcatalyst.sfnt import INPUT_EXTENSIONS

PROG = "fontcatalyst"
DOCS_HINT = "https://andrewsipe.github.io/FontCatalyst/"

PANEL_MESSAGE = (
    "Decompresses WOFF and WOFF2 to the TTF or OTF inside them, then reports "
    "a structural check. Sources stay put unless you pass -c or -ct, which "
    "move successes into a converted folder and originals into _archive. "
    "_quarantine is created only when a file fails."
)
PANEL_ROWS = (
    ("Beside each source", "default"),
    ("Per-folder sort", "-c, --consolidate [DIR]"),
    ("One top-level sort", "-ct, --consolidate-top [DIR]"),
    ("Apply a recommended fix", "--repair"),
)

EXAMPLES = [
    ("fontcatalyst fonts/ -r", "unwrap webfonts and review"),
    ("fontcatalyst fonts/ -r -ct", "sort into _converted_top, _archive, _quarantine"),
    ("fontcatalyst fonts/ -r --repair", "also apply coverage fixes or a TTX rebuild"),
    ("fontcatalyst convert --to woff2 fonts/", "lossless wrap as WOFF2"),
]

NOTES = [
    "A pass keeps the decompressed file. Questionable notes do not trigger a rewrite.",
    "A fail names one repair — structure (coverage / PairPos) or ttx (table would not decompile) — or lists required tables that are absent. Missing tables are not repaired.",
    "--repair runs only that repair. Healthy files are not sent through TTX.",
    "With -c or -ct, successes move to the converted folder and originals to _archive. "
    "_quarantine is created only for a hard failure, and the error line includes the reason.",
]

SUBCOMMANDS = {
    "convert": "One target per run: lossless WOFF/WOFF2 wrap, or TTF to OTF. fontcatalyst convert --help",
}

# What each convert target actually does. Shown under --to, and echoed on the result line.
CONVERT_TARGETS = {
    "woff": "Lossless zlib wrap of the SFNT already in the file. Outlines and hints stay.",
    "woff2": "Lossless Brotli wrap of that same SFNT. Outlines and hints stay.",
    "otf": "Lossy. Refits TrueType outlines as CFF and drops TrueType instructions.",
}

CONVERT_EXAMPLES = [
    ("fontcatalyst convert --to woff2 fonts/", "lossless Brotli wrap"),
    ("fontcatalyst convert --to woff fonts/", "lossless zlib wrap"),
    ("fontcatalyst convert --to otf Family.ttf", "TTF to OTF; prints the fidelity warning"),
]

CONVERT_NOTES = [
    "Each run writes one target. WOFF and WOFF2 only change the container.",
    "A webfont is unwrapped first, then wrapped again. The SFNT tables are not rebuilt.",
    "--to otf refits TrueType outlines as CFF (tolerance 0.001 em) and drops TrueType instructions. It is not a cubic master.",
    "OTF to TTF is refused. Variable TTF to variable OTF is refused.",
    "With -c or -ct, the new file goes to the converted folder and the original to _archive. "
    "_quarantine is created only for a hard failure.",
]

EXIT_CODES = {
    # A per-file refusal (already CFF, variable TTF, missing glyf, etc.) is an
    # "error" outcome on that one file; it does not change the process exit
    # code. Only an empty file list does.
    "0": "finished (individual files may still be fail or error)",
    "1": "no TTF, OTF, WOFF, or WOFF2 files found",
}


def _shared(g_in: argparse._ArgumentGroup, g_out: argparse._ArgumentGroup) -> None:
    g_in.add_argument("paths", nargs="+", metavar="PATH", help="font files or directories")
    g_in.add_argument("-r", "--recursive", action="store_true", help="recurse into directories")
    g_out.add_argument("-o", "--output-dir", type=Path, metavar="DIR", help="write results to DIR; leave sources in place")
    g_out.add_argument(
        "-c", "--consolidate", nargs="?", const="_converted", metavar="DIR",
        help="per source folder: DIR for results, plus _archive and _quarantine (default DIR: _converted)",
    )
    g_out.add_argument(
        "-ct", "--consolidate-top", nargs="?", const="_converted_top", type=Path, metavar="DIR",
        help="one result folder, with _archive and _quarantine beside it (default: _converted_top)",
    )
    g_out.add_argument(
        "-j", "--jobs", type=int, default=1, metavar="N",
        help="reserved for parallel runs (this version processes files in order)",
    )


def _help_kwargs(
    panel_message: str,
    panel_rows: tuple[tuple[str, str], ...],
    *,
    examples: list[tuple[str, str]] = EXAMPLES,
    notes: list[str] = NOTES,
    extra_footer: tuple = (),
    inline: dict | None = None,
):
    console = cs.get_console()
    return dict(
        action=RichHelp,
        console=console,
        help="show this help message and exit",
        panel=safety_panel(panel_message, panel_rows),
        inline=inline,
        footer=[
            examples_section(examples),
            *extra_footer,
            notes_section(notes),
            exit_status_section(EXIT_CODES),
            line_section("formats", "TTF, OTF, WOFF, WOFF2"),
            docs_section(DOCS_HINT),
        ],
    )


def build_ingest_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROG,
        description=(
            "Font Catalyst: decompress WOFF/WOFF2 to the embedded TTF or OTF, "
            "then report a structural check."
        ),
        add_help=False,
        allow_abbrev=False,
    )
    # Group *creation* order is display order (argparse), independent of when
    # arguments are added to each group below. Input/output first, since
    # they apply to every run; "general" (-h/--version) last, by convention.
    g_in = parser.add_argument_group("input")
    g_out = parser.add_argument_group("output and sorting")
    g_review = parser.add_argument_group("review")
    g_gen = parser.add_argument_group("general")

    _shared(g_in, g_out)
    g_review.add_argument(
        "--repair",
        action="store_true",
        help="apply the one repair named by the check (coverage sort, or a TTX rebuild)",
    )
    g_gen.add_argument(
        "-h", "--help",
        **_help_kwargs(
            PANEL_MESSAGE,
            PANEL_ROWS,
            extra_footer=(choices_section("subcommands", SUBCOMMANDS),),
        ),
    )
    g_gen.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


CONVERT_PANEL = (
    "Secondary command. Each run writes one target. WOFF and WOFF2 wrap the "
    "SFNT that is already in the file. TTF to OTF refits outlines and drops "
    "TrueType hinting."
)
CONVERT_ROWS = (
    ("Lossless wrap", "--to woff / --to woff2"),
    ("TTF to OTF", "--to otf"),
    ("Folder sort", "-c / -ct"),
)


def build_convert_parser() -> argparse.ArgumentParser:
    """Subcommand parser. Dispatched from main() when argv starts with convert.

    The default command stays bare (`fontcatalyst PATH`) because it owns the
    PATH positional. Putting both on one argparse parser makes `convert` look
    like a font path. This parser is still a real subcommand: its own groups,
    --help, and --version.
    """
    parser = argparse.ArgumentParser(
        prog=f"{PROG} convert",
        description=(
            "Wrap an SFNT as WOFF or WOFF2, or convert TrueType outlines to CFF. "
            "One target per run."
        ),
        add_help=False,
        allow_abbrev=False,
    )
    g_in = parser.add_argument_group("input")
    g_target = parser.add_argument_group("conversion target")
    g_out = parser.add_argument_group("output and sorting")
    g_gen = parser.add_argument_group("general")

    _shared(g_in, g_out)
    g_target.add_argument(
        "--to",
        required=True,
        choices=tuple(CONVERT_TARGETS),
        help="woff or woff2 (lossless wrap), or otf (TTF outlines to CFF)",
    )
    g_gen.add_argument(
        "-h", "--help",
        **_help_kwargs(
            CONVERT_PANEL,
            CONVERT_ROWS,
            examples=CONVERT_EXAMPLES,
            notes=CONVERT_NOTES,
            inline={"conversion target": choices_section("what --to does", CONVERT_TARGETS)},
        ),
    )
    g_gen.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return parser


def _collect(args) -> list[Path]:
    found = list(
        iter_font_files(
            paths=args.paths,
            recursive=args.recursive,
            allowed_extensions=INPUT_EXTENSIONS,
        )
    )
    return [Path(item) for item in found]


def _top_and_slots_args(args):
    output_dir = args.output_dir.resolve() if args.output_dir else None
    consolidate_top = None
    if args.consolidate_top:
        top = common_parent([Path(p) for p in args.paths])
        name = str(args.consolidate_top)
        if not name.startswith("_"):
            name = "_" + name
        consolidate_top = top / Path(name).name
    return output_dir, args.consolidate, consolidate_top


def _run(paths: list[Path], args, runner) -> int:
    if not paths:
        emit("error", "No TTF, OTF, WOFF, or WOFF2 files found.")
        return 1
    output_dir, consolidate, consolidate_top = _top_and_slots_args(args)
    if consolidate_top:
        emit(
            "pass",
            f"Sorting into {consolidate_top.name} and _archive.",
        )
    counts = {"pass": 0, "fail": 0, "error": 0}
    quarantine_dirs: set[Path] = set()
    for path in paths:
        slots = slots_for(
            path,
            output_dir=output_dir,
            consolidate=consolidate,
            consolidate_top=consolidate_top,
        )
        if slots.quarantine is not None:
            quarantine_dirs.add(slots.quarantine)
        outcome = runner(path, slots)
        counts[outcome.status] = counts.get(outcome.status, 0) + 1
        emit_outcome(outcome)
    for folder in quarantine_dirs:
        remove_if_empty(folder)
    emit(
        "pass",
        f"Done. pass {counts['pass']}, fail {counts['fail']}, error {counts['error']}.",
    )
    return 0


def main(argv: list[str] | None = None) -> None:
    try:
        os.getcwd()
    except PermissionError:
        os.chdir(Path.home())

    argv = list(sys.argv[1:] if argv is None else argv)
    # `convert` is the only subcommand. Match it before the default parser so
    # the word is not taken as a PATH.
    if argv and argv[0] == "convert":
        parser = build_convert_parser()
        args = parser.parse_args(argv[1:])
        paths = _collect(args)
        code = _run(
            paths,
            args,
            lambda path, slots: convert_file(path, slots, args.to),
        )
        sys.exit(code)

    parser = build_ingest_parser()
    args = parser.parse_args(argv)
    paths = _collect(args)
    code = _run(
        paths,
        args,
        lambda path, slots: ingest_file(path, slots, args.repair),
    )
    sys.exit(code)


if __name__ == "__main__":
    main()
