"""Limited conversions: wrap to WOFF/WOFF2, and TTF to OTF.

OTF to TTF is refused. Variable TTF to variable OTF is refused.
"""

from __future__ import annotations

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.basePen import BasePen
from fontTools.pens.qu2cuPen import Qu2CuPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.ttLib import TTFont

from fontcatalyst.sfnt import decompress, is_cff, is_variable

TTF_ONLY_TABLES = ("glyf", "cvt ", "loca", "fpgm", "prep", "gasp", "LTSH", "hdmx")
OTF_ERROR_EM = 0.001


class ConvertError(Exception):
    """A conversion this tool will not perform, with the reason."""


class NothingToDo(ConvertError):
    """The file is already what --to asked for. Not a failure."""


def wrap(font: TTFont, flavor: str) -> list[str]:
    """Set flavor to 'woff' or 'woff2'. Call save() after.

    Returns the clarification lines to print. The SFNT tables are not rebuilt.
    """
    if flavor not in {"woff", "woff2"}:
        raise ConvertError(f"Unknown web flavor {flavor!r}.")
    source = font.flavor
    if source == flavor:
        raise NothingToDo(
            f"Already {flavor}. No conversion necessary."
        )
    variable = is_variable(font)
    decompress(font)
    font.flavor = flavor
    if source in {"woff", "woff2"}:
        notes = [
            f"Recompressed the embedded SFNT from {source} to {flavor}. "
            "Outlines and hints unchanged."
        ]
    else:
        notes = [
            f"Wrapped the SFNT as {flavor}. Outlines and hints unchanged."
        ]
    if variable and flavor == "woff":
        notes.append(
            "Variable font. WOFF2 is the container variable fonts are usually published in."
        )
    return notes


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
        raise NothingToDo("Font is already CFF. Nothing to convert.")
    if "glyf" not in font:
        raise ConvertError("Font has no TrueType glyf table to convert.")
    if is_variable(font):
        raise ConvertError(
            "Variable TTF to variable OTF is not supported. "
            "Decompress a variable webfont to keep the variable TTF as-is."
        )

    decompress(font)
    glyf, hmtx = _snapshot_outlines(font)
    overlap = _remove_overlaps(font)
    try:
        charstrings = _charstrings(font)
    except Exception as exc:
        if overlap != "Overlaps removed.":
            raise
        _restore_outlines(font, glyf, hmtx)
        charstrings = _charstrings(font)
        overlap = (
            "Overlap removal skipped. The simplified contours could not be "
            f"refit as cubics ({type(exc).__name__}), so the original contours were refit."
        )
    notes.append(overlap)

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

    notes.append(_subroutinize(font))
    return notes


def _charstrings(font: TTFont) -> dict:
    glyph_set = font.getGlyphSet()
    max_err = OTF_ERROR_EM * font["head"].unitsPerEm
    charstrings = {}
    for name in font.getGlyphOrder():
        glyph = glyph_set[name]
        t2 = T2CharStringPen(glyph.width, glyph_set)
        cubic = Qu2CuPen(t2, max_err=max_err, all_cubic=True)
        # Overlap removal can leave a quadratic contour with no on-curve points.
        # Qu2CuPen refuses those. Make each implied on-curve point explicit first.
        glyph.draw(_ExplicitOnCurvePen(cubic, glyph_set))
        charstrings[name] = t2.getCharString()
    return charstrings


class _ExplicitOnCurvePen(BasePen):
    """Forward a contour after TrueType implied on-curve points are filled in."""

    def __init__(self, out, glyph_set):
        super().__init__(glyph_set)
        self._out = out

    def _moveTo(self, pt):
        self._out.moveTo(pt)

    def _lineTo(self, pt):
        self._out.lineTo(pt)

    def _curveToOne(self, pt1, pt2, pt3):
        self._out.curveTo(pt1, pt2, pt3)

    def _qCurveToOne(self, pt1, pt2):
        self._out.qCurveTo(pt1, pt2)

    def _closePath(self):
        self._out.closePath()

    def _endPath(self):
        self._out.endPath()


def _snapshot_outlines(font: TTFont) -> tuple[bytes, bytes | None]:
    glyf = font["glyf"].compile(font)
    hmtx = font["hmtx"].compile(font) if "hmtx" in font else None
    return glyf, hmtx


def _restore_outlines(font: TTFont, glyf: bytes, hmtx: bytes | None) -> None:
    font["glyf"].decompile(glyf, font)
    if hmtx is not None:
        font["hmtx"].decompile(hmtx, font)


def _remove_overlaps(font: TTFont) -> str:
    """Merge overlapping TrueType contours. The refit still runs if this cannot."""
    try:
        from fontTools.ttLib.removeOverlaps import removeOverlaps
    except ImportError:
        return "Overlap removal skipped (skia-pathops is not installed)."
    glyf, hmtx = _snapshot_outlines(font)
    try:
        removeOverlaps(font, ignoreErrors=True)
    except Exception as exc:
        _restore_outlines(font, glyf, hmtx)
        return f"Overlap removal skipped ({exc}). The original contours were refit."
    return "Overlaps removed."


def _subroutinize(font: TTFont) -> str:
    """Share repeated CFF pieces. A failure keeps the larger, unshared CFF."""
    try:
        import cffsubr
    except ImportError:
        return "CFF subroutinization skipped (cffsubr is not installed)."
    compiled = font["CFF "].compile(font)
    try:
        cffsubr.subroutinize(font)
    except Exception as exc:
        from fontTools.ttLib import newTable

        table = newTable("CFF ")
        table.decompile(compiled, font)
        font["CFF "] = table
        return f"CFF subroutinization skipped ({exc}). The larger CFF was kept."
    return "CFF subroutinized."
