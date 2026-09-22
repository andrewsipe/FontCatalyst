"""Coverage + PairPos pre-sort for Font Catalyst (vendored from Opentype_Tools).

Sorts Coverage tables by GlyphID before TTX round-trip to reduce common
convert failures. PairPos second-glyph order is repaired as in FontCore
`core_gpos_repair`. Failures are non-fatal at the call site.
"""

from __future__ import annotations

from typing import Iterator, List, Tuple

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables as ot


def get_glyph_id(font: TTFont, glyph_name: str) -> int:
    try:
        return font.getGlyphID(glyph_name)
    except (KeyError, ValueError, AttributeError):
        return 2**31 - 1


def iter_expand_subtables(subtables) -> Iterator:
    """Yield subtables, recursing into ExtensionPos wrappers."""
    for subtable in subtables:
        ext = getattr(subtable, "ExtSubTable", None)
        if ext is not None:
            yield from iter_expand_subtables([ext])
        else:
            yield subtable


def repair_pairpos_second_glyph_order(
    font: TTFont,
) -> List[Tuple[int, str, List[str], List[str]]]:
    """Sort PairPos Format 1 PairValueRecord entries by second-glyph glyph ID."""
    if "GPOS" not in font:
        return []

    fixes: List[Tuple[int, str, List[str], List[str]]] = []
    table = font["GPOS"].table

    for lookup_index, lookup in enumerate(table.LookupList.Lookup):
        if lookup.LookupType != 9:
            continue
        for subtable in iter_expand_subtables(lookup.SubTable):
            if not isinstance(subtable, ot.PairPos) or subtable.Format != 1:
                continue
            if not subtable.Coverage or not subtable.Coverage.glyphs:
                continue
            for first_glyph, pairset in zip(subtable.Coverage.glyphs, subtable.PairSet):
                records = getattr(pairset, "PairValueRecord", None)
                if not records or len(records) < 2:
                    continue
                old_order = [record.SecondGlyph for record in records]
                records.sort(key=lambda record: get_glyph_id(font, record.SecondGlyph))
                new_order = [record.SecondGlyph for record in records]
                if new_order != old_order:
                    fixes.append((lookup_index, first_glyph, old_order, new_order))
    return fixes


def sort_coverage(font: TTFont, coverage) -> bool:
    if not hasattr(coverage, "glyphs") or not coverage.glyphs:
        return False
    old_glyphs = list(coverage.glyphs)
    glyph_data = [(get_glyph_id(font, g), g) for g in coverage.glyphs]
    glyph_data.sort(key=lambda x: x[0])
    coverage.glyphs = [g for _, g in glyph_data]
    return old_glyphs != coverage.glyphs


def sort_class_def(font: TTFont, class_def) -> bool:
    if not hasattr(class_def, "classDefs") or not class_def.classDefs:
        return False
    old_items = list(class_def.classDefs.items())
    sorted_items = sorted(
        class_def.classDefs.items(), key=lambda x: get_glyph_id(font, x[0])
    )
    class_def.classDefs = dict(sorted_items)
    return old_items != sorted_items


def process_lookup(font: TTFont, lookup) -> int:
    sorted_count = 0
    if not hasattr(lookup, "SubTable"):
        return sorted_count

    for subtable in iter_expand_subtables(lookup.SubTable):
        cov = getattr(subtable, "Coverage", None)
        pair_sets = getattr(subtable, "PairSet", None)
        lig_keys = getattr(subtable, "ligatures", None)

        if (
            cov is not None
            and hasattr(cov, "glyphs")
            and cov.glyphs
            and pair_sets is not None
        ):
            try:
                old_glyphs = list(cov.glyphs)
                if sort_coverage(font, cov):
                    sorted_count += 1
                new_glyphs = cov.glyphs
                old_to_new = {}
                for old_idx, glyph in enumerate(old_glyphs):
                    if glyph in new_glyphs:
                        new_idx = new_glyphs.index(glyph)
                        old_to_new[old_idx] = new_idx
                if (
                    pair_sets
                    and len(old_to_new) == len(old_glyphs)
                    and len(old_to_new) == len(new_glyphs)
                ):
                    old_pairset = subtable.PairSet[:]
                    new_pairset = [None] * len(old_pairset)
                    for old_idx, new_idx in old_to_new.items():
                        if old_idx < len(old_pairset):
                            new_pairset[new_idx] = old_pairset[old_idx]
                    if None not in new_pairset:
                        subtable.PairSet = new_pairset
            except (AttributeError, TypeError, ValueError):
                pass
        elif (
            cov is not None
            and hasattr(cov, "glyphs")
            and cov.glyphs
            and lig_keys is not None
        ):
            try:
                if sort_coverage(font, cov):
                    sorted_count += 1
                new_glyphs = cov.glyphs
                old_ligatures = subtable.ligatures.copy()
                new_ligatures = {}
                for glyph in new_glyphs:
                    if glyph in old_ligatures:
                        new_ligatures[glyph] = old_ligatures[glyph]
                subtable.ligatures = new_ligatures
            except (AttributeError, TypeError):
                pass
        elif cov is not None:
            if sort_coverage(font, cov):
                sorted_count += 1

        if hasattr(subtable, "ClassDef"):
            sort_class_def(font, subtable.ClassDef)

        if hasattr(subtable, "BacktrackCoverage"):
            for c in subtable.BacktrackCoverage:
                if sort_coverage(font, c):
                    sorted_count += 1

        if hasattr(subtable, "InputCoverage"):
            for c in subtable.InputCoverage:
                if sort_coverage(font, c):
                    sorted_count += 1

        if hasattr(subtable, "LookAheadCoverage"):
            for c in subtable.LookAheadCoverage:
                if sort_coverage(font, c):
                    sorted_count += 1

    return sorted_count


def process_table(font: TTFont, table_tag: str) -> Tuple[int, int]:
    total_coverage = 0
    sorted_count = 0

    if table_tag not in font:
        return total_coverage, sorted_count

    table = font[table_tag]
    if hasattr(table, "table"):
        table = table.table

    if hasattr(table, "LookupList") and table.LookupList:
        for lookup in table.LookupList.Lookup:
            if hasattr(lookup, "SubTable"):
                for subtable in lookup.SubTable:
                    if hasattr(subtable, "Coverage") and hasattr(
                        subtable.Coverage, "glyphs"
                    ):
                        if subtable.Coverage.glyphs:
                            total_coverage += 1
                    if hasattr(subtable, "BacktrackCoverage"):
                        total_coverage += len(subtable.BacktrackCoverage)
                    if hasattr(subtable, "InputCoverage"):
                        total_coverage += len(subtable.InputCoverage)
                    if hasattr(subtable, "LookAheadCoverage"):
                        total_coverage += len(subtable.LookAheadCoverage)
            sorted_count += process_lookup(font, lookup)

    return total_coverage, sorted_count


def process_gdef(font: TTFont) -> Tuple[int, int]:
    total_coverage = 0
    sorted_count = 0

    if "GDEF" not in font:
        return total_coverage, sorted_count

    gdef = font["GDEF"].table

    if hasattr(gdef, "LigCaretList") and gdef.LigCaretList:
        lig_caret = gdef.LigCaretList
        if hasattr(lig_caret, "Coverage") and hasattr(lig_caret.Coverage, "glyphs"):
            if lig_caret.Coverage.glyphs:
                total_coverage += 1
                old_glyphs = list(lig_caret.Coverage.glyphs)
                if sort_coverage(font, lig_caret.Coverage):
                    sorted_count += 1
                new_glyphs = lig_caret.Coverage.glyphs

                if hasattr(lig_caret, "LigGlyph") and lig_caret.LigGlyph and old_glyphs:
                    old_lig_glyphs = lig_caret.LigGlyph[:]
                    new_lig_glyphs = [None] * len(old_lig_glyphs)

                    for i, old_glyph in enumerate(old_glyphs):
                        if old_glyph in new_glyphs and i < len(old_lig_glyphs):
                            new_idx = new_glyphs.index(old_glyph)
                            new_lig_glyphs[new_idx] = old_lig_glyphs[i]

                    if None in new_lig_glyphs:
                        lig_caret.LigGlyph = [
                            lg for lg in new_lig_glyphs if lg is not None
                        ]
                    else:
                        lig_caret.LigGlyph = new_lig_glyphs

    if hasattr(gdef, "AttachList") and gdef.AttachList:
        if hasattr(gdef.AttachList, "Coverage") and hasattr(
            gdef.AttachList.Coverage, "glyphs"
        ):
            if gdef.AttachList.Coverage.glyphs:
                total_coverage += 1
                if sort_coverage(font, gdef.AttachList.Coverage):
                    sorted_count += 1

    if hasattr(gdef, "MarkAttachClassDef") and gdef.MarkAttachClassDef:
        sort_class_def(font, gdef.MarkAttachClassDef)

    if hasattr(gdef, "GlyphClassDef") and gdef.GlyphClassDef:
        sort_class_def(font, gdef.GlyphClassDef)

    return total_coverage, sorted_count


def sort_coverage_tables_in_font(
    font: TTFont, verbose: bool = False
) -> Tuple[int, int]:
    """Sort all Coverage tables in a font by glyph ID (in place)."""
    total_coverage = 0
    sorted_count = 0

    gsub_total, gsub_sorted = process_table(font, "GSUB")
    total_coverage += gsub_total
    sorted_count += gsub_sorted

    gpos_total, gpos_sorted = process_table(font, "GPOS")
    total_coverage += gpos_total
    sorted_count += gpos_sorted

    gdef_total, gdef_sorted = process_gdef(font)
    total_coverage += gdef_total
    sorted_count += gdef_sorted

    pairpos_fixes = repair_pairpos_second_glyph_order(font)
    sorted_count += len(pairpos_fixes)

    return total_coverage, sorted_count
