"""Read-only structural review. Does not rewrite the font."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO

from fontTools.ttLib import TTFont

from fontcatalyst.coverage_sort import sort_coverage_tables_in_font


@dataclass
class Review:
    level: str  # good, questionable, bad
    repair: str | None = None  # structure, ttx
    lines: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.level != "bad"


# Spec minimum for a font that can install and draw. Optional layout and
# hinting tables (GSUB, GPOS, gasp, kern) are intentionally not listed.
_REQUIRED_TTF = ("cmap", "glyf", "head", "hhea", "hmtx", "loca", "maxp", "name", "post", "OS/2")
_REQUIRED_CFF = ("cmap", "head", "hhea", "hmtx", "maxp", "name", "post", "OS/2")


def review_font(font: TTFont, checksum_note: str | None = None) -> Review:
    """Classify a loaded SFNT.

    Good and questionable both mean: keep this file, do not rewrite it.
    Bad means either a repair this tool knows, or a required table is absent.
    A missing table is not repairable here.
    """
    lines: list[str] = []
    decompile_error = _first_decompile_error(font)
    if decompile_error:
        return Review("bad", "ttx", [decompile_error])

    missing = _missing_required(font)
    if missing:
        listed = ", ".join(missing)
        return Review(
            "bad",
            None,
            [f"Missing required table(s): {listed}. No repair in this tool can add them."],
        )

    if is_color := _color_note(font):
        lines.append(is_color)

    structure = _structure_change_count(font)
    if structure is None:
        return Review(
            "bad",
            "ttx",
            lines + ["Could not probe coverage tables; a TTX rebuild may recover the file."],
        )
    if structure > 0:
        lines.append(
            f"Coverage or PairPos order can be corrected ({structure} change(s))."
        )
        return Review("bad", "structure", lines)

    if checksum_note:
        lines.append(checksum_note)

    if lines:
        return Review("questionable", None, lines)
    return Review("good", None, [f"{_outline(font)} outlines"])


def _missing_required(font: TTFont) -> list[str]:
    if "CFF " in font or "CFF2" in font:
        needed = list(_REQUIRED_CFF)
    elif "glyf" in font:
        needed = list(_REQUIRED_TTF)
    else:
        return ["glyf or CFF"]
    missing = [tag for tag in needed if tag not in font]
    if "fvar" in font and "gvar" not in font and "CFF2" not in font:
        missing.append("gvar or CFF2")
    return missing


def _outline(font: TTFont) -> str:
    from fontcatalyst.sfnt import outline_label

    return outline_label(font)


def _first_decompile_error(font: TTFont) -> str | None:
    for tag in list(font.keys()):
        try:
            font[tag]
        except Exception as exc:
            return f"Table {tag!r} would not decompile: {exc}"
    return None


def _color_note(font: TTFont) -> str | None:
    present = [tag.strip() for tag in ("COLR", "CPAL", "CBDT", "CBLC", "sbix", "SVG ") if tag in font]
    if not present:
        return None
    return "Color or bitmap tables present (" + ", ".join(present) + "); left unchanged."


def _structure_change_count(font: TTFont) -> int | None:
    try:
        buf = BytesIO()
        saved_flavor = font.flavor
        font.flavor = None
        font.save(buf)
        font.flavor = saved_flavor
        buf.seek(0)
        probe = TTFont(buf, lazy=False)
        try:
            _total, changed = sort_coverage_tables_in_font(probe, verbose=False)
            return changed
        finally:
            probe.close()
    except Exception:
        return None


def checksums_fail(path) -> str | None:
    """Return a message when stored table checksums do not match, else None."""
    try:
        TTFont(path, lazy=False, checkChecksums=2)
    except AssertionError as exc:
        return str(exc)
    except Exception:
        return None
    return None
