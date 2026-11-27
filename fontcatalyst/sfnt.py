"""Load fonts and describe the embedded SFNT."""

from __future__ import annotations

from pathlib import Path

from fontTools.ttLib import TTFont

from FontCore.core_coverage_sort import watch_unsorted_coverage

SFNT_EXTENSIONS = {".ttf", ".otf"}
WEB_EXTENSIONS = {".woff", ".woff2"}
INPUT_EXTENSIONS = SFNT_EXTENSIONS | WEB_EXTENSIONS


def load_font(path: Path) -> TTFont:
    """Open a font. Raises fontTools / OSError with a message on failure.

    head.modified stays the time stored in the file. A later save does not
    rewrite it to the moment the file was processed.
    """
    with watch_unsorted_coverage() as watch:
        font = TTFont(path, lazy=False, recalcTimestamp=False)
    # fontTools repairs an out-of-order Coverage as it reads, so the review would see a sorted font; remember it was not
    font.coverage_was_unsorted = watch.fired
    return font


def is_cff(font: TTFont) -> bool:
    return "CFF " in font or "CFF2" in font


def is_variable(font: TTFont) -> bool:
    return "fvar" in font


def sfnt_suffix(font: TTFont) -> str:
    """Extension for the uncompressed SFNT, based on outline type."""
    return ".otf" if is_cff(font) else ".ttf"


def outline_label(font: TTFont) -> str:
    if "CFF2" in font:
        kind = "CFF2"
    elif "CFF " in font:
        kind = "CFF"
    elif "glyf" in font:
        kind = "TrueType"
    else:
        kind = "unknown outlines"
    if is_variable(font):
        return f"variable {kind}"
    return kind


def decompress(font: TTFont) -> None:
    """Drop WOFF/WOFF2 packaging. Table bytes stay as they were."""
    font.flavor = None
    font.flavorData = None
