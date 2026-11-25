"""A font is skipped as "from an earlier run" because this tool wrote it there, not because of its folder's name."""

from test_generated_folders import flat, listing, make, run

from fontcatalyst import provenance


def test_record_then_recognise_then_forget_when_changed(tmp_path):
    font = make(tmp_path / "out" / "a.ttf")
    assert not provenance.is_ours(font)
    provenance.record(font)
    assert provenance.is_ours(font)
    font.write_bytes(font.read_bytes() + b"\0")  # edited since: no longer what we wrote
    assert not provenance.is_ours(font)


def test_a_new_font_dropped_into_an_output_folder_is_processed(tmp_path):
    make(tmp_path / "Fam" / "a.ttf")
    assert run("-c", "-r", tmp_path / "Fam").returncode == 0  # a.ttf is now in Fam/_converted
    make(tmp_path / "Fam" / "_converted" / "mine.ttf")  # the user's own font, never written by the tool
    result = run("-r", tmp_path)
    out = flat(result)
    assert "Converted 1" in out and "Skipped 1 font" in out, out  # mine.ttf runs, a.ttf (ours) is skipped


def test_outputs_in_a_folder_with_any_name_are_recognised(tmp_path):
    from test_generated_folders import make_woff

    make_woff(tmp_path / "Fam" / "a.woff")
    outdir = tmp_path / "Fam" / "web_ready"
    assert run("-o", outdir, tmp_path / "Fam" / "a.woff").returncode == 0  # writes web_ready/a.ttf
    assert provenance.is_ours(outdir / "a.ttf")
    result = run("-r", tmp_path)
    out = flat(result)
    assert "Skipped 1 font" in out, out  # web_ready/a.ttf is ours; the woff beside it is processed again


def test_folders_from_before_manifests_still_skip_by_name(tmp_path):
    make(tmp_path / "Fam" / "_converted" / "old.ttf")  # no manifest anywhere: an older run's folder
    result = run("-r", tmp_path)
    assert result.returncode == 1 and "--include-generated" in flat(result)
