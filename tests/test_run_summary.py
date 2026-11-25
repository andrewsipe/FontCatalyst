"""A run ends with one sentence, a warning chip when anything went wrong, and exit 1 for any problem."""

from test_generated_folders import flat, make, run


def test_clean_run_says_no_problems_and_exits_0(tmp_path):
    make(tmp_path / "a.ttf")
    r = run("convert", "-2", "woff", tmp_path)
    assert r.returncode == 0
    assert "Converted 1, no problems." in flat(r)


def test_unreadable_font_is_a_problem_and_exit_1(tmp_path):
    make(tmp_path / "a.ttf")
    (tmp_path / "Broken.ttf").write_bytes((tmp_path / "a.ttf").read_bytes()[:120])
    r = run("convert", "-2", "woff", tmp_path)
    text = flat(r)
    assert r.returncode == 1, text
    assert "Converted 1, 1 problem." in text
    assert "WARNING" in text and "SUCCESS" not in text.split("Converted")[0].split("Finished")[-1]
