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
    assert result.returncode == 0 and "Converted 2" in flat(result)


def test_naming_the_generated_folder_itself_works(tmp_path):
    make(tmp_path / "Normal" / "_converted" / "a.ttf")
    result = run("-r", tmp_path / "Normal" / "_converted")
    assert result.returncode == 0 and "Converted 1" in flat(result)


def test_a_mixed_tree_processes_the_rest_and_says_what_it_skipped(tmp_path):
    make(tmp_path / "top.ttf")
    make(tmp_path / "Fam" / "deep.ttf")
    make(tmp_path / "Fam" / "_archive" / "old.ttf")
    result = run("-r", tmp_path)
    out = flat(result)
    assert result.returncode == 0 and "Converted 2" in out
    assert "Skipped 1 font" in out and "--include-generated" in out


def test_a_folder_with_no_fonts_still_gets_the_plain_message(tmp_path):
    (tmp_path / "empty").mkdir()
    out = flat(run("-r", tmp_path))
    assert "No TTF, OTF, WOFF, or WOFF2 files found" in out


def test_the_help_lists_the_flag():
    assert "--include-generated" in flat(run("-h"))


# ---- -ct gathers the folders an earlier -c run made --------------------------------------------------------

def make_woff(path: Path) -> Path:
    from fontTools.ttLib import TTFont

    ttf = make(path.with_suffix(".ttf"))
    font = TTFont(ttf)
    font.flavor = "woff"
    font.save(str(path))
    ttf.unlink()
    return path


def listing(root: Path):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file() and p.name != ".DS_Store")


def two_families(tmp_path):
    for fam in ("Normal", "Wide"):
        for style in ("Regular", "Bold"):
            make_woff(tmp_path / fam / f"{fam}-{style}.woff")


def test_ct_after_c_gathers_everything_without_converting_twice(tmp_path):
    two_families(tmp_path)
    assert run("-c", "-r", tmp_path).returncode == 0
    result = run("-ct", "-r", tmp_path)
    out = flat(result)
    assert result.returncode == 0, out
    assert listing(tmp_path) == [
        "_archive/Normal-Bold.woff", "_archive/Normal-Regular.woff", "_archive/Wide-Bold.woff", "_archive/Wide-Regular.woff",
        "_converted_top/Normal-Bold.ttf", "_converted_top/Normal-Regular.ttf", "_converted_top/Wide-Bold.ttf", "_converted_top/Wide-Regular.ttf",
    ]
    assert "Collected 8 fonts" in out and "#1" not in out
    # the emptied folders from the first pass are gone
    assert not (tmp_path / "Normal" / "_converted").exists() and not (tmp_path / "Wide" / "_archive").exists()


def test_ct_gathers_earlier_folders_and_converts_new_files_in_one_run(tmp_path):
    two_families(tmp_path)
    run("-c", "-r", tmp_path)
    make_woff(tmp_path / "Extra" / "Extra-Regular.woff")
    result = run("-ct", "-r", tmp_path)
    assert result.returncode == 0, flat(result)
    files = listing(tmp_path)
    assert "_converted_top/Extra-Regular.ttf" in files and "_archive/Extra-Regular.woff" in files
    assert len([f for f in files if f.startswith("_converted_top/")]) == 5
    assert not [f for f in files if "#" in f]


def test_a_second_ct_pass_changes_nothing(tmp_path):
    two_families(tmp_path)
    run("-c", "-r", tmp_path)
    run("-ct", "-r", tmp_path)
    before = listing(tmp_path)
    run("-ct", "-r", tmp_path)
    assert listing(tmp_path) == before


def test_c_still_leaves_earlier_folders_alone(tmp_path):
    two_families(tmp_path)
    run("-c", "-r", tmp_path)
    before = listing(tmp_path)
    run("-c", "-r", tmp_path)
    assert listing(tmp_path) == before


def test_ttx_ct_after_ttx_c_gathers_the_ttx_folders(tmp_path):
    for fam in ("Normal", "Wide"):
        make(tmp_path / fam / f"{fam}-Regular.ttf")
    assert run("ttx", "-c", "-r", tmp_path).returncode == 0
    result = run("ttx", "-ct", "-r", tmp_path)
    assert result.returncode == 0, flat(result)
    files = listing(tmp_path)
    assert "_ttx_top/Normal-Regular.ttx" in files and "_ttx_top/Wide-Regular.ttx" in files
    assert not (tmp_path / "Normal" / "_ttx").exists()


# ---- naming the earlier-run folder itself ---------------------------------------------------------------

def test_ct_on_an_earlier_run_folder_itself_is_an_ordinary_pass_not_a_collection(tmp_path):
    folder = tmp_path / "_converted"
    make(folder / "a.ttf")
    make_woff(folder / "b.woff")
    result = run("-ct", "-r", folder)
    out = flat(result)
    assert "Traceback" not in out and result.returncode == 0, out
    assert "Collected" not in out  # the folder you name is the source, not something to gather
    files = listing(folder)
    assert "_converted_top/a.ttf" in files and "_converted_top/b.ttf" in files and "_archive/b.woff" in files


def test_a_file_that_vanishes_mid_run_is_an_error_line_not_a_crash(tmp_path, monkeypatch, capsys):
    import pytest

    import fontcatalyst.cli as cli

    make(tmp_path / "a.ttf")
    make(tmp_path / "b.ttf")
    real = cli.ingest_file

    def flaky(path, slots, repair):
        if path.name == "a.ttf":
            path.unlink()  # gone before it is read
        return real(path, slots, repair)

    monkeypatch.setattr(cli, "ingest_file", flaky)
    monkeypatch.setattr(sys, "argv", ["fontcatalyst", str(tmp_path)])
    with pytest.raises(SystemExit) as stopped:
        cli.main()
    out = " ".join((capsys.readouterr().out).split())
    assert stopped.value.code == 1
    assert "a.ttf" in out and "Converted 1" in out and "1 problem" in out  # b was still processed; a is reported
