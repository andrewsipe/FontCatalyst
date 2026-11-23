"""Fonts inside folders from an earlier run (_converted, _archive, ...) are skipped on purpose; say so, and let the user include them."""

import subprocess
import sys
from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

ROOT = Path(__file__).resolve().parents[1]


def make(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fb = FontBuilder(1000, isTTF=True)
    fb.setupGlyphOrder([".notdef"])
    fb.setupCharacterMap({})
    fb.setupGlyf({".notdef": TTGlyphPen(None).glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "P", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.save(path)
    return path


def run(*args):
    return subprocess.run(
        [sys.executable, "-m", "fontcatalyst", *map(str, args)],
        capture_output=True, text=True, cwd=ROOT, timeout=300, stdin=subprocess.DEVNULL,
    )


def flat(result):
    return " ".join((result.stdout + result.stderr).split())


def test_all_fonts_in_earlier_run_folders_says_why_and_what_to_do(tmp_path):
    make(tmp_path / "Normal" / "_converted" / "a.otf.ttf")
    make(tmp_path / "Expanded" / "_converted" / "b.ttf")
    result = run("-r", tmp_path)
    out = flat(result)
    assert result.returncode == 1
    assert "No TTF, OTF, WOFF, or WOFF2 files found" not in out
    assert "2 fonts" in out and "_converted" in out and "--include-generated" in out


def test_include_generated_processes_them(tmp_path):
    make(tmp_path / "Normal" / "_converted" / "a.ttf")
    make(tmp_path / "Expanded" / "_converted" / "b.ttf")
    result = run("-r", "--include-generated", tmp_path)
    assert result.returncode == 0 and "pass 2" in flat(result)


def test_naming_the_generated_folder_itself_works(tmp_path):
    make(tmp_path / "Normal" / "_converted" / "a.ttf")
    result = run("-r", tmp_path / "Normal" / "_converted")
    assert result.returncode == 0 and "pass 1" in flat(result)


def test_a_mixed_tree_processes_the_rest_and_says_what_it_skipped(tmp_path):
    make(tmp_path / "top.ttf")
    make(tmp_path / "Fam" / "deep.ttf")
    make(tmp_path / "Fam" / "_archive" / "old.ttf")
    result = run("-r", tmp_path)
    out = flat(result)
    assert result.returncode == 0 and "pass 2" in out
    assert "Skipped 1 font" in out and "--include-generated" in out


def test_a_folder_with_no_fonts_still_gets_the_plain_message(tmp_path):
    (tmp_path / "empty").mkdir()
    out = flat(run("-r", tmp_path))
    assert "No TTF, OTF, WOFF, or WOFF2 files found" in out


def test_the_help_lists_the_flag():
    assert "--include-generated" in flat(run("-h"))
