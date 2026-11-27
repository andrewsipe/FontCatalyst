"""Merge new GSUB rules into an existing font without replacing the table.

fontTools ``addOpenTypeFeaturesFromString`` replaces entire OTL tables. Connect
apply must append lookups in place so existing features are preserved.
"""

from __future__ import annotations

import re
from collections import OrderedDict
from typing import Dict, List, Tuple

from fontTools.otlLib.builder import LigatureSubstBuilder, SingleSubstBuilder
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables import otTables

from .feature_extraction import ExistingSubstitutionExtractor
from .wrapper_helpers import create_gsub, empty_otl_table

_FEATURE_BLOCK_RE = re.compile(
    r"feature\s+(\w+)\s*\{(.*?)\}\s*\1\s*;",
    re.DOTALL | re.IGNORECASE,
)
_SUB_RULE_RE = re.compile(
    r"^\s*sub\s+(.+?)\s+by\s+(\S+)\s*;\s*$",
    re.MULTILINE,
)


def _ensure_gsub_table(font: TTFont) -> otTables.GSUB:
    if "GSUB" not in font:
        create_gsub(font, overwrite=False)
    gsub = font["GSUB"].table
    if gsub.LookupList is None:
        gsub.LookupList = otTables.LookupList()
        gsub.LookupList.Lookup = []
        gsub.LookupList.LookupCount = 0
    if gsub.FeatureList is None:
        gsub.FeatureList = otTables.FeatureList()
        gsub.FeatureList.FeatureRecord = []
        gsub.FeatureList.FeatureCount = 0
    if gsub.ScriptList is None:
        gsub.ScriptList = otTables.ScriptList()
        gsub.ScriptList.ScriptRecord = []
        gsub.ScriptList.ScriptCount = 0
    return gsub


def _ensure_default_script(gsub: otTables.GSUB) -> None:
    if gsub.ScriptList.ScriptCount:
        return
    srec = otTables.ScriptRecord()
    srec.ScriptTag = "latn"
    srec.Script = otTables.Script()
    langsys = otTables.LangSys()
    langsys.LookupOrder = None
    langsys.ReqFeatureIndex = 0xFFFF
    langsys.FeatureIndex = []
    langsys.FeatureCount = 0
    srec.Script.DefaultLangSys = langsys
    srec.Script.LangSysRecord = []
    srec.Script.LangSysCount = 0
    gsub.ScriptList.ScriptRecord = [srec]
    gsub.ScriptList.ScriptCount = 1


def _find_feature_index(gsub: otTables.GSUB, feature_tag: str) -> int | None:
    for idx, frec in enumerate(gsub.FeatureList.FeatureRecord or []):
        if frec.FeatureTag == feature_tag:
            return idx
    return None


def _register_feature_in_scripts(gsub: otTables.GSUB, feature_index: int) -> None:
    _ensure_default_script(gsub)
    for srec in gsub.ScriptList.ScriptRecord:
        lang_systems: List[otTables.LangSys] = []
        if srec.Script.DefaultLangSys is not None:
            lang_systems.append(srec.Script.DefaultLangSys)
        for langrec in srec.Script.LangSysRecord or []:
            if langrec.LangSys is not None:
                lang_systems.append(langrec.LangSys)
        for langsys in lang_systems:
            indices = list(langsys.FeatureIndex or [])
            if feature_index not in indices:
                indices.append(feature_index)
                langsys.FeatureIndex = indices
                langsys.FeatureCount = len(indices)


def _append_lookup(gsub: otTables.GSUB, lookup: otTables.Lookup) -> int:
    gsub.LookupList.Lookup.append(lookup)
    gsub.LookupList.LookupCount = len(gsub.LookupList.Lookup)
    return len(gsub.LookupList.Lookup) - 1


def _attach_lookup_to_feature(gsub: otTables.GSUB, feature_tag: str, lookup_idx: int) -> None:
    feat_idx = _find_feature_index(gsub, feature_tag)
    if feat_idx is None:
        frec = otTables.FeatureRecord()
        frec.FeatureTag = feature_tag
        frec.Feature = otTables.Feature()
        frec.Feature.LookupListIndex = [lookup_idx]
        frec.Feature.LookupCount = 1
        gsub.FeatureList.FeatureRecord.append(frec)
        feat_idx = len(gsub.FeatureList.FeatureRecord) - 1
        gsub.FeatureList.FeatureCount = len(gsub.FeatureList.FeatureRecord)
        _register_feature_in_scripts(gsub, feat_idx)
        return

    frec = gsub.FeatureList.FeatureRecord[feat_idx]
    indices = list(frec.Feature.LookupListIndex or [])
    if lookup_idx not in indices:
        indices.append(lookup_idx)
        frec.Feature.LookupListIndex = indices
        frec.Feature.LookupCount = len(indices)


def _block_is_contextual(block_body: str) -> bool:
    for line in block_body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "'" in stripped or "ignore" in stripped:
            return True
        if "[" in stripped or "]" in stripped:
            return True
    return False


def parse_simple_feature_rules(
    fea_content: str,
) -> Tuple[Dict[str, Dict[str, list]], List[str]]:
    """
    Parse simple GSUB rules from FEA text.

    Returns:
        ({tag: {"subs": [(in, out)], "ligs": [(components, out)]}}, contextual_tags)
    """
    features: Dict[str, Dict[str, list]] = {}
    contextual_tags: List[str] = []

    for match in _FEATURE_BLOCK_RE.finditer(fea_content):
        tag = match.group(1)
        body = match.group(2)
        if _block_is_contextual(body):
            contextual_tags.append(tag)
            continue

        bucket = features.setdefault(tag, {"subs": [], "ligs": []})
        for rule_match in _SUB_RULE_RE.finditer(body):
            left = rule_match.group(1).strip()
            right = rule_match.group(2).strip()
            if left.startswith("[") or "@" in left:
                contextual_tags.append(tag)
                bucket["subs"].clear()
                bucket["ligs"].clear()
                break
            glyphs = left.split()
            if len(glyphs) == 1:
                bucket["subs"].append((glyphs[0], right))
            elif len(glyphs) >= 2:
                bucket["ligs"].append((tuple(glyphs), right))

    contextual_tags = sorted(set(contextual_tags))
    return features, contextual_tags


def _suffix_rank(glyph: str, patterns: Tuple[str, ...]):
    """Index of the first naming suffix in ``patterns`` the glyph ends with, or None for a name no suffix explains."""
    for rank, pattern in enumerate(patterns):
        if glyph.endswith(pattern):
            return rank
    return None


def _feature_single_mappings(gsub: otTables.GSUB, feature_tag: str) -> Dict[str, Tuple[dict, str]]:
    """input glyph -> (that lookup's mapping dict, output glyph) for the single substitutions this feature already runs."""
    found: Dict[str, Tuple[dict, str]] = {}
    lookups = gsub.LookupList.Lookup if getattr(gsub, "LookupList", None) else []
    for rec in getattr(getattr(gsub, "FeatureList", None), "FeatureRecord", None) or []:
        if rec.FeatureTag != feature_tag:
            continue
        for idx in rec.Feature.LookupListIndex or []:
            if idx >= len(lookups):
                continue
            for st in lookups[idx].SubTable:
                st = getattr(st, "ExtSubTable", None) or st
                mapping = getattr(st, "mapping", None)
                if isinstance(mapping, dict):
                    for inp, out in mapping.items():
                        found.setdefault(inp, (mapping, out))  # the first lookup to touch a glyph is the one that fires
    return found


def merge_single_substitutions(
    font: TTFont,
    feature_tag: str,
    pairs: List[Tuple[str, str]],
) -> Tuple[int, int]:
    """Add new single substitutions to a feature. Returns (added, replaced).

    A feature maps an input glyph to one output, and the first rule to match fires. So a glyph the feature already
    maps is left alone, unless the old output is a naming-suffix variant and the new one ranks higher for this feature
    (eight.onum over eight.tosf for onum): then the old rule is replaced in place. An output with no suffix the policy
    knows is the designer's choice and is never touched."""
    if not pairs:
        return 0, 0

    from .feature_policy import policy_by_tag

    entry = policy_by_tag().get(feature_tag)
    patterns = tuple(entry.patterns) if entry and getattr(entry, "patterns", None) else ()

    existing = ExistingSubstitutionExtractor(font).extract_all()["single"]
    in_feature = _feature_single_mappings(font["GSUB"].table, feature_tag) if "GSUB" in font else {}

    new_pairs = []
    replaced = 0
    seen_inputs = set()
    for a, b in pairs:
        if (a, b) in existing or a in seen_inputs:  # one output per input: the first listed wins, never the last
            continue
        seen_inputs.add(a)
        if a in in_feature:
            mapping, old = in_feature[a]
            old_rank, new_rank = _suffix_rank(old, patterns), _suffix_rank(b, patterns)
            if old != b and old_rank is not None and new_rank is not None and new_rank < old_rank:
                mapping[a] = b
                replaced += 1
            continue  # already mapped here: a second rule for it would never fire
        new_pairs.append((a, b))
    if not new_pairs:
        return 0, replaced

    gsub = _ensure_gsub_table(font)
    builder = SingleSubstBuilder(font, "connect")
    builder.mapping = OrderedDict(new_pairs)
    lookup = builder.build()
    lookup_idx = _append_lookup(gsub, lookup)
    _attach_lookup_to_feature(gsub, feature_tag, lookup_idx)
    return len(new_pairs), replaced


def merge_ligature_substitutions(
    font: TTFont,
    feature_tag: str,
    ligatures: List[Tuple[Tuple[str, ...], str]],
) -> int:
    """Append a type-4 lookup with new ligatures. Returns count added."""
    if not ligatures:
        return 0

    existing = ExistingSubstitutionExtractor(font).extract_all()["ligatures"]
    new_ligs = [(c, g) for c, g in ligatures if c not in existing]
    if not new_ligs:
        return 0

    gsub = _ensure_gsub_table(font)
    builder = LigatureSubstBuilder(font, "connect")
    builder.ligatures = OrderedDict(new_ligs)
    lookup = builder.build()
    lookup_idx = _append_lookup(gsub, lookup)
    _attach_lookup_to_feature(gsub, feature_tag, lookup_idx)
    return len(new_ligs)


def merge_gsub_from_fea(font: TTFont, fea_content: str) -> Tuple[bool, List[str]]:
    """
    Append simple substitution/ligature rules from FEA into existing GSUB.

    Contextual feature blocks are skipped (reported in messages).
    """
    messages: List[str] = []
    features, contextual_tags = parse_simple_feature_rules(fea_content)

    if contextual_tags:
        messages.append(
            "Skipped contextual features (not safe to auto-merge): "
            + ", ".join(contextual_tags)
        )

    if not features:
        if contextual_tags:
            return True, messages
        return False, ["No mergeable substitution rules found in FEA"]

    total = 0
    for tag, rules in sorted(features.items()):
        sub_count, replaced = merge_single_substitutions(font, tag, rules.get("subs", []))
        lig_count = merge_ligature_substitutions(font, tag, rules.get("ligs", []))
        added = sub_count + lig_count
        if added:
            messages.append(f"Merged {added} rule(s) into feature '{tag}'")
        if replaced:
            messages.append(f"Replaced {replaced} rule(s) in feature '{tag}' with a better-ranked variant")
        total += added + replaced

    if total == 0 and not contextual_tags:
        messages.append("No new substitutions to merge (all already present)")

    return True, messages
