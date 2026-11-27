"""Read-only layout structure checks: what scan and verify report about GSUB/GPOS that connect cannot change."""

from __future__ import annotations

import copy

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib import newTable

from fontcatalyst.opentype.structure_checks import find_structure_notes
from otl.conftest import minimal_font


def _font(fea="", cmap=None, names=(".notdef", "a", "b", "acutecomb")):
    font = minimal_font(list(names))
    if cmap:
        fb = FontBuilder(font=font)
        fb.setupCharacterMap(cmap)
    if fea:
        addOpenTypeFeaturesFromString(font, fea)
    return font


def _codes(font):
    return {n.code for n in find_structure_notes(font)}


def test_a_clean_font_reports_nothing():
    assert _codes(_font("feature liga { sub a b by a; } liga;")) == set()


def test_an_unused_lookup_is_reported():
    font = _font("feature ss01 { sub a by b; } ss01;")
    lookups = font["GSUB"].table.LookupList
    lookups.Lookup.append(copy.deepcopy(lookups.Lookup[0]))
    lookups.LookupCount = len(lookups.Lookup)
    assert "gsub-unused-lookup" in _codes(font)


def test_a_feature_pointing_at_a_missing_lookup_is_an_error():
    font = _font("feature ss01 { sub a by b; } ss01;")
    font["GSUB"].table.FeatureList.FeatureRecord[0].Feature.LookupListIndex.append(40)
    notes = find_structure_notes(font)
    assert any(n.code == "gsub-broken-reference" and n.severity == "error" for n in notes)


def test_contextual_lookups_are_listed_by_feature():
    font = _font("feature calt { sub a' b by b; } calt;")
    notes = [n for n in find_structure_notes(font) if n.code == "gsub-contextual"]
    assert notes and "calt (1)" in notes[0].message


def test_a_legacy_kern_table_without_gpos_kern_is_reported():
    font = _font()
    font["kern"] = newTable("kern")
    font["kern"].kernTables = []
    assert "legacy-kern-only" in _codes(font)


def test_combining_marks_without_a_mark_feature_are_noted():
    font = _font("feature kern { pos a b -20; } kern;", cmap={0x61: "a", 0x301: "acutecomb"})
    assert "no-mark-positioning" in _codes(font)


def test_a_lookup_used_only_by_feature_variations_is_not_unused():
    from fontTools.ttLib.tables import otTables as ot

    font = _font("feature ss01 { sub a by b; } ss01;")
    gsub = font["GSUB"].table
    lookups = gsub.LookupList
    lookups.Lookup.append(copy.deepcopy(lookups.Lookup[0]))
    lookups.LookupCount = len(lookups.Lookup)

    feature = ot.Feature()
    feature.FeatureParams = None
    feature.LookupListIndex = [1]
    feature.LookupCount = 1
    sub = ot.FeatureTableSubstitutionRecord()
    sub.FeatureIndex = 0
    sub.Feature = feature
    fts = ot.FeatureTableSubstitution()
    fts.Version = 0x00010000
    fts.SubstitutionRecord = [sub]
    fts.SubstitutionCount = 1
    rec = ot.FeatureVariationRecord()
    rec.ConditionSet = None
    rec.FeatureTableSubstitution = fts
    fv = ot.FeatureVariations()
    fv.Version = 0x00010000
    fv.FeatureVariationRecord = [rec]
    fv.FeatureVariationCount = 1
    gsub.FeatureVariations = fv
    assert "gsub-unused-lookup" not in _codes(font)
