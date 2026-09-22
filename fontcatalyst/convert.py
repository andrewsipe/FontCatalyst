"""Limited conversions: wrap to WOFF/WOFF2, and TTF to OTF.

OTF to TTF is refused. Variable TTF to variable OTF is refused.
"""

from __future__ import annotations

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

from fontcatalyst.sfnt import decompress, is_cff, is_variable

TTF_ONLY_TABLES = ("glyf", "cvt ", "loca", "fpgm", "prep", "gasp", "LTSH", "hdmx")
OTF_ERROR_EM = 0.001


class ConvertError(Exception):
    """A conversion this tool will not perform, with the reason."""


def wrap(font: TTFont, flavor: str) -> None:
    """Set flavor to 'woff' or 'woff2'. Call save() after."""
    if flavor not in {"woff", "woff2"}:
        raise ConvertError(f"Unknown web flavor {flavor!r}.")
    decompress(font)
    font.flavor = flavor


def ttf_to_otf(font: TTFont) -> list[str]:
    """Replace TrueType outlines with a CFF table. Returns warning lines.

    Mutates `font` into an OTF-flavored SFNT (sfntVersion OTTO).
    """
    notes = [
        "TTF to OTF refits quadratic outlines as cubics (tolerance 0.001 em). "
        "TrueType instructions and gasp/hdmx tables are dropped. "
        "This is not a cubic master."
    ]
    if is_cff(font):
        raise ConvertError("Font is already CFF (.otf). Nothing to convert.")
    if "glyf" not in font:
        raise ConvertError("Font has no TrueType glyf table to convert.")
    if is_variable(font):
        raise ConvertError(
            "Variable TTF to variable OTF is not supported. "
            "Decompress a variable webfont to keep the variable TTF as-is."
        )

    decompress(font)
    overlap_note = _remove_overlaps(font)
    if overlap_note:
        notes.append(overlap_note)

    glyph_set = font.getGlyphSet()
    upm = font["head"].unitsPerEm
    max_err = OTF_ERROR_EM * upm
    charstrings = {}
    for name in font.getGlyphOrder():
        glyph = glyph_set[name]
        t2 = T2CharStringPen(glyph.width, glyph_set)
        pen = Qu2CuPen(t2, max_err=max_err, all_cubic=True)
        glyph.draw(pen)
        charstrings[name] = t2.getCharString()

    for tag in TTF_ONLY_TABLES:
        if tag in font:
            del font[tag]
    if "DSIG" in font:
        del font["DSIG"]

    ps_name = font["name"].getDebugName(6) or "Untitled"
    post = font["post"]
    name = font["name"]
    revision = font["head"].fontRevision
    font_info = {
        "version": f"{revision:.3f}",
        "FullName": name.getBestFullName() or ps_name,
        "FamilyName": name.getBestFamilyName() or ps_name,
        "ItalicAngle": post.italicAngle,
        "UnderlinePosition": post.underlinePosition,
        "UnderlineThickness": post.underlineThickness,
        "isFixedPitch": bool(post.isFixedPitch),
    }

    builder = FontBuilder(font=font)
    builder.isTTF = False
    builder.setupGlyphOrder(font.getGlyphOrder())
    builder.setupCFF(
        psName=ps_name,
        fontInfo=font_info,
        charStringsDict=charstrings,
        privateDict={},
    )
    builder.setupMaxp()

    subr = _subroutinize(font)
    if subr:
        notes.append(subr)
    return notes


def _remove_overlaps(font: TTFont) -> str | None:
    try:
        from fontTools.ttLib.removeOverlaps import removeOverlaps

        removeOverlaps(font, ignoreErrors=True)
    except ImportError:
        return "Overlap removal skipped (skia-pathops is not installed)."
    except Exception as exc:
        return f"Overlap removal skipped: {exc}"
    return None


def _subroutinize(font: TTFont) -> str | None:
    try:
        import cffsubr
    except ImportError:
        return "CFF subroutinization skipped (cffsubr is not installed)."
    try:
        cffsubr.subroutinize(font)
    except Exception as exc:
        return f"CFF subroutinization skipped: {exc}"
    return None
