"""Repairs Font Catalyst will actually run. Each one matches a review finding."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from fontTools.ttLib import TTFont

from fontcatalyst.coverage_sort import sort_coverage_tables_in_font
from fontcatalyst.sfnt import decompress, sfnt_suffix


def apply_structure(font: TTFont) -> int:
    """Sort coverage tables and PairPos records in memory. Returns change count."""
    _total, changed = sort_coverage_tables_in_font(font, verbose=False)
    return changed


def dump_ttx(source: Path, dest: Path) -> None:
    """Write `source` to `dest` as TTX XML. Raises RuntimeError on failure.

    The binary font is not rebuilt. `ttx` itself accepts one file; callers
    walk directories.
    """
    if not ttx_available():
        raise RuntimeError(
            "ttx command not found. Install fonttools so the ttx executable is on PATH."
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dump = subprocess.run(
        ["ttx", "-q", "-o", str(dest), str(source)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    if dump.returncode != 0 or not dest.is_file():
        raise RuntimeError(_ttx_failure("dump", dump.stderr))


def rebuild_with_ttx(font: TTFont) -> TTFont:
    """Round-trip through TTX and return the rebuilt font.

    Raises RuntimeError with the ttx stderr (or a short reason) on failure.
    """
    if not ttx_available():
        raise RuntimeError(
            "ttx command not found. Install fonttools so the ttx executable is on PATH."
        )

    with tempfile.TemporaryDirectory(prefix="fontcatalyst_ttx_") as tmp:
        folder = Path(tmp)
        source = folder / f"source{sfnt_suffix(font)}"
        decompress(font)
        font.save(source)
        ttx_path = folder / "source.ttx"

        dump = subprocess.run(
            ["ttx", "-q", "-o", str(ttx_path), str(source)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if dump.returncode != 0:
            raise RuntimeError(_ttx_failure("dump", dump.stderr))

        compile_run = subprocess.run(
            ["ttx", "-q", str(ttx_path)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        if compile_run.returncode != 0:
            raise RuntimeError(_ttx_failure("compile", compile_run.stderr))

        produced = _find_sfnt(ttx_path.with_suffix(""))
        if produced is None:
            raise RuntimeError("ttx compile finished without a .ttf or .otf.")
        rebuilt = TTFont(produced, lazy=False)
        return rebuilt


def ttx_available() -> bool:
    try:
        subprocess.run(["ttx", "-h"], capture_output=True, check=True, timeout=5)
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _ttx_failure(step: str, stderr: str) -> str:
    detail = (stderr or "").strip()
    if not detail:
        detail = "no error text from ttx"
    return f"ttx {step} failed: {detail}"


def _find_sfnt(base: Path) -> Path | None:
    for suffix in (".ttf", ".otf"):
        candidate = base.with_suffix(suffix)
        if candidate.exists():
            return candidate
    return None
