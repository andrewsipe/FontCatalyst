"""Character variants (cvNN) and stylistic-set glyph names are detected, scanned and written into the plan."""

from __future__ import annotations

from fontcatalyst.opentype.analyze import analyze_font
from fontcatalyst.opentype.connect import build_connect_plan, render_connect_fea
from fontcatalyst.opentype.detection import UnifiedGlyphDetector
from fontcatalyst.opentype.models import ConnectOptions
from otl.conftest import add_empty_otl_shell, minimal_font


def _features(names):
    return UnifiedGlyphDetector(minimal_font([".notdef", *names])).get_features()


def test_character_variants_are_grouped_by_number():
    cv = _features(["a", "a.cv01", "g", "g.cv01", "g.cv02"])["character_variants"]
    assert cv[1] == [("a", "a.cv01"), ("g", "g.cv01")] or sorted(cv[1]) == [("a", "a.cv01"), ("g", "g.cv01")]
    assert cv[2] == [("g", "g.cv02")]


def test_a_variant_without_its_base_glyph_is_ignored():
    assert _features(["a.cv01"])["character_variants"] == {}


def test_ss_names_accept_one_digit_and_any_case():
    ss = _features(["a", "a.ss7", "b", "b.SS03"])["stylistic_sets"]
    assert ss[7] == [("a", "a.ss7")] and ss[3] == [("b", "b.SS03")]


def test_a_cv_variant_is_not_also_read_as_a_stylistic_set():
    assert _features(["a", "a.cv01"])["stylistic_sets"] == {}


def test_connect_writes_a_cv_feature():
    font = minimal_font([".notdef", "a", "a.cv01", "a.ss01"])
    add_empty_otl_shell(font)
    audit = analyze_font(font, __import__("pathlib").Path("T.ttf"))
    assert "cv01" in audit.stylistic_sets and "ss01" in audit.stylistic_sets
    plan = build_connect_plan(audit, ConnectOptions())
    fea = render_connect_fea(audit, plan, font)
    assert "feature cv01 {" in fea and "sub a by a.cv01;" in fea


def test_a_base_with_two_variants_gets_the_first_suffix_in_the_list():
    from fontcatalyst.opentype.feature_policy import detect_single_pairs

    names = {"one", "one.onum", "one.osf", "two", "two.osf"}
    pairs = detect_single_pairs(names, (".onum", ".osf"))
    assert sorted(pairs) == [("one", "one.onum"), ("two", "two.osf")]
