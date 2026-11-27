"""connect replaces a lower-ranked variant in a feature instead of adding a rule that would never fire."""

from __future__ import annotations

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

from fontcatalyst.opentype.gsub_merge import merge_single_substitutions
from otl.conftest import minimal_font


def _font(fea):
    font = minimal_font([".notdef", "one", "one.onum", "one.tosf", "two", "two.onum", "two.mine"])
    addOpenTypeFeaturesFromString(font, fea)
    return font


def _map(font, tag):
    gsub = font["GSUB"].table
    out = {}
    for fr in gsub.FeatureList.FeatureRecord:
        if fr.FeatureTag == tag:
            for i in fr.Feature.LookupListIndex:
                for st in gsub.LookupList.Lookup[i].SubTable:
                    out.update(st.mapping)
    return out


def test_a_lower_ranked_variant_is_replaced_in_place():
    font = _font("feature onum { sub one by one.tosf; } onum;")
    added, replaced = merge_single_substitutions(font, "onum", [("one", "one.onum")])
    assert (added, replaced) == (0, 1)
    assert _map(font, "onum")["one"] == "one.onum"


def test_a_designers_own_mapping_is_not_touched():
    font = _font("feature onum { sub two by two.mine; } onum;")
    assert merge_single_substitutions(font, "onum", [("two", "two.onum")]) == (0, 0)
    assert _map(font, "onum")["two"] == "two.mine"


def test_an_unmapped_glyph_is_added():
    font = _font("feature onum { sub one by one.onum; } onum;")
    assert merge_single_substitutions(font, "onum", [("two", "two.onum")]) == (1, 0)
