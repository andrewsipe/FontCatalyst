"""Ligature detection is the same on every run and ignores stylistic variants of a ligature."""

from __future__ import annotations

from fontcatalyst.opentype.detection import UnifiedGlyphDetector
from otl.conftest import minimal_font


def _liga(names):
    font = minimal_font([".notdef", "f", "i", "l", *names])
    return UnifiedGlyphDetector(font).get_features()["liga"]


def test_a_stylistic_variant_of_a_ligature_is_not_a_liga_candidate():
    liga = _liga(["fi", "fi.ss07", "fi.ss07.ss05", "fl", "fl.ss07"])
    assert sorted(g for _c, g in liga) == ["fi", "fl"]


def test_the_plain_name_wins_over_a_dotted_liga_name():
    liga = _liga(["fi.liga", "fi"])
    assert [g for _c, g in liga] == ["fi"]


def test_candidates_follow_the_font_glyph_order():
    liga = _liga(["fl", "fi"])
    assert [g for _c, g in liga] == ["fl", "fi"]
