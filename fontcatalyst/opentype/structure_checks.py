"""Read-only checks on how GSUB and GPOS are put together.

``connect`` only adds simple substitutions and ligatures. Everything here is outside what it can change, so these are
reported, never fixed: broken or unused lookups, features no script reaches, kerning that is not wired, marks that
cannot attach, and the contextual lookups that connect leaves alone.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, List, Set

from fontTools.ttLib import TTFont

from .models import StructureNote

# Real lookup types (after unwrapping extensions) that are contextual.
_CONTEXTUAL = {"GSUB": {5, 6, 8}, "GPOS": {7, 8}}
_EXTENSION = {"GSUB": 7, "GPOS": 9}
_PAIR = 2  # GPOS pair adjustment (kerning)
_MARK_TAGS = {"mark", "mkmk", "abvm", "blwm"}
_COMBINING = range(0x0300, 0x0370)


def _real_type(table: str, lookup) -> int:
    if lookup.LookupType == _EXTENSION[table]:
        for st in lookup.SubTable:
            real = getattr(st, "ExtensionLookupType", None)
            if real:
                return real
    return lookup.LookupType


def _subtables(lookup):
    for st in lookup.SubTable:
        yield getattr(st, "ExtSubTable", None) or st


def _nested_indices(obj, depth: int = 0) -> Iterable[int]:
    """LookupListIndex values in a contextual subtable's nested records."""
    if depth > 6:
        return
    if isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _nested_indices(item, depth + 1)
        return
    attrs = getattr(obj, "__dict__", None)
    if not attrs:
        return
    for name, value in attrs.items():
        if name == "LookupListIndex" and isinstance(value, int):
            yield value
        elif isinstance(value, (list, tuple)) or hasattr(value, "__dict__"):
            yield from _nested_indices(value, depth + 1)


def _walk_table(font: TTFont, table: str, notes: List[StructureNote]) -> Dict[str, object]:
    """Checks that need one table's lookup and feature lists. Returns facts the cross-table checks use."""
    facts: Dict[str, object] = {"tags": set(), "pair_used": False, "mark_flag_lookups": 0}
    if table not in font:
        return facts
    t = font[table].table
    lookups = list(getattr(getattr(t, "LookupList", None), "Lookup", None) or [])
    features = list(getattr(getattr(t, "FeatureList", None), "FeatureRecord", None) or [])
    n = len(lookups)
    if not lookups and not features:
        return facts

    real = [_real_type(table, lk) for lk in lookups]
    used_by_feature: Dict[int, Set[str]] = defaultdict(set)
    broken: Set[str] = set()
    for rec in features:
        facts["tags"].add(rec.FeatureTag)
        for idx in (getattr(rec.Feature, "LookupListIndex", None) or []):
            if idx >= n:
                broken.add(f"{rec.FeatureTag}→{idx}")
            else:
                used_by_feature[idx].add(rec.FeatureTag)

    nested_used: Set[int] = set()
    # Variable fonts swap in other lookups through FeatureVariations (rvrn and the like); those are in use too.
    fv = getattr(t, "FeatureVariations", None)
    for vr in (getattr(fv, "FeatureVariationRecord", None) or []):
        subst = getattr(vr, "FeatureTableSubstitution", None)
        for sub in (getattr(subst, "SubstitutionRecord", None) or []):
            for idx in (getattr(sub.Feature, "LookupListIndex", None) or []):
                if idx < n:
                    nested_used.add(idx)
    for i, lk in enumerate(lookups):
        if real[i] in _CONTEXTUAL[table]:
            for st in _subtables(lk):
                for idx in _nested_indices(st):
                    if idx >= n:
                        broken.add(f"lookup {i}→{idx}")
                    else:
                        nested_used.add(idx)
        if lk.LookupFlag & 0x00FE or lk.LookupFlag & 0xFF00:
            facts["mark_flag_lookups"] += 1

    if broken:
        notes.append(StructureNote("error", f"{table.lower()}-broken-reference",
            f"{table}: {len(broken)} reference(s) to lookups that do not exist ({', '.join(sorted(broken)[:4])})"))

    orphans = [i for i in range(n) if i not in used_by_feature and i not in nested_used]
    if orphans:
        shown = ", ".join(str(i) for i in orphans[:6]) + (" …" if len(orphans) > 6 else "")
        notes.append(StructureNote("warning", f"{table.lower()}-unused-lookup",
            f"{table}: {len(orphans)} lookup(s) no feature uses (index {shown}); they do nothing"))
        if table == "GPOS" and any(real[i] == _PAIR for i in orphans):
            notes.append(StructureNote("warning", "kerning-not-wired",
                "GPOS: pair-kerning lookup(s) exist but no feature points at them; kerning is not applied"))

    facts["pair_used"] = any(real[i] == _PAIR for i in used_by_feature)

    reached: Set[int] = set()
    sl = getattr(t, "ScriptList", None)
    script_records = list(getattr(sl, "ScriptRecord", None) or [])
    for sr in script_records:
        langs = [sr.Script.DefaultLangSys] if getattr(sr.Script, "DefaultLangSys", None) else []
        langs += [lr.LangSys for lr in (getattr(sr.Script, "LangSysRecord", None) or [])]
        for ls in langs:
            reached.update(getattr(ls, "FeatureIndex", None) or [])
            req = getattr(ls, "ReqFeatureIndex", 0xFFFF)
            if req != 0xFFFF:
                reached.add(req)
    if script_records:
        lost = sorted({rec.FeatureTag for i, rec in enumerate(features) if i not in reached})
        if lost:
            notes.append(StructureNote("warning", f"{table.lower()}-feature-unreachable",
                f"{table}: feature(s) no script lists: {', '.join(lost[:8])}; apps will not offer them"))

    contextual: Dict[str, int] = defaultdict(int)
    for i, lk in enumerate(lookups):
        if real[i] in _CONTEXTUAL[table]:
            for tag in used_by_feature.get(i, {"(called by another lookup)"}):
                contextual[tag] += 1
    if contextual:
        listing = ", ".join(f"{tag} ({count})" for tag, count in sorted(contextual.items()))
        notes.append(StructureNote("info", f"{table.lower()}-contextual",
            f"{table}: contextual lookups connect and aalt leave alone: {listing}"))
    return facts


def find_structure_notes(font: TTFont) -> List[StructureNote]:
    """Never raises: these are advisory, so an odd table must not stop an audit."""
    notes: List[StructureNote] = []
    try:
        _find(font, notes)
    except Exception as e:  # noqa: BLE001
        notes.append(StructureNote("info", "structure-check-skipped", f"Layout structure could not be checked ({e})"))
    return notes


def _find(font: TTFont, notes: List[StructureNote]) -> None:
    gsub = _walk_table(font, "GSUB", notes)
    gpos = _walk_table(font, "GPOS", notes)

    if "kern" in font and "kern" not in gpos["tags"]:
        notes.append(StructureNote("warning", "legacy-kern-only",
            "Kerning is only in the old 'kern' table; there is no GPOS kern feature (many apps ignore it)"))

    marks = _MARK_TAGS & gpos["tags"]
    if "mark" not in marks:
        cmap = font.getBestCmap() or {}
        combining = [cp for cp in cmap if cp in _COMBINING]
        if combining:
            notes.append(StructureNote("info", "no-mark-positioning",
                f"{len(combining)} combining mark(s) in cmap but no GPOS mark feature; marks will not attach to letters"))

    if (marks or gsub["mark_flag_lookups"] or gpos["mark_flag_lookups"]):
        gdef = font["GDEF"].table if "GDEF" in font else None
        if gdef is None or getattr(gdef, "GlyphClassDef", None) is None:
            notes.append(StructureNote("warning", "no-glyph-classes",
                "Mark features or mark-filtering lookups exist but GDEF has no glyph classes; marks may not be recognised"))
