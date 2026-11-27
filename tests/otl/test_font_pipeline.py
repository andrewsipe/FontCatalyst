"""The per-font features pipeline: dry run leaves files alone, a run saves once, one bad font does not stop the rest."""

from __future__ import annotations

from fontcatalyst.opentype.flow_commands import prepare_context
from fontcatalyst.opentype.flow_context import FlowContext
from fontcatalyst.opentype.font_pipeline import Steps, run_pipeline
from otl.conftest import minimal_font


def _font(path, names=("f", "i", "fi")):
    from fontTools.fontBuilder import FontBuilder

    order = [".notdef", *names]
    fb = FontBuilder(1000, isTTF=True)
    empty = minimal_font(order)["glyf"][".notdef"]
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({0x66: "f", 0x69: "i"})
    fb.setupGlyf({n: empty for n in order})
    fb.setupHorizontalMetrics({n: (500, 0) for n in order})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "T", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(path)
    return path


def _ctx(tmp_path, **kw):
    ctx = FlowContext(paths=[str(tmp_path)], recursive=True, yes=True, **kw)
    assert prepare_context(ctx) == 0
    return ctx


def test_dry_run_changes_nothing(tmp_path):
    path = _font(tmp_path / "A.ttf")
    before = path.read_bytes()
    assert run_pipeline(_ctx(tmp_path, dry_run=True), Steps()) in (0, 1)
    assert path.read_bytes() == before


def test_a_bad_file_does_not_stop_the_run(tmp_path, capsys):
    (tmp_path / "Bad.ttf").write_bytes(b"not a font")
    _font(tmp_path / "Good.ttf")
    ctx = _ctx(tmp_path)
    rc = run_pipeline(ctx, Steps())
    assert rc == 1  # the bad file counts as an error
    out = capsys.readouterr().out
    assert "[2/2]" in out  # the second font was still reached


def test_a_font_that_needs_work_is_saved_once(tmp_path):
    from fontTools.ttLib import TTFont

    path = _font(tmp_path / "A.ttf")
    assert "GSUB" not in TTFont(path)
    assert run_pipeline(_ctx(tmp_path), Steps()) == 0
    assert "GSUB" in TTFont(path)  # wrapped and saved


def test_the_gdef_class_warning_is_summarised_not_repeated(tmp_path, capsys):
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    from fontTools.ttLib import TTFont

    for name in ("A.ttf", "B.ttf"):
        path = _font(tmp_path / name)
        font = TTFont(path)
        addOpenTypeFeaturesFromString(font, "feature kern { lookupflag IgnoreMarks; pos f i -20; } kern;")
        font.save(path)
    run_pipeline(_ctx(tmp_path, dry_run=True), Steps(wrap=False, connect=False, aalt=False, sort=False))
    out = capsys.readouterr().out
    assert out.count("no GDEF glyph classes") == 1
