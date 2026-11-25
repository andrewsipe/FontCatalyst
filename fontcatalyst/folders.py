"""Output folders for the default run and for -c / -ct."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from fontcatalyst import provenance


@dataclass
class Slots:
    """Where a result file is written, and where the source moves.

    `archive` and `quarantine` are set only for -c / -ct, which empty the
    source folder into those directories plus the converted output.
    """

    output: Path
    archive: Path | None
    quarantine: Path | None


def next_free(path: Path) -> Path:
    if not path.exists():
        return path
    stem, suffix, folder = path.stem, path.suffix, path.parent
    n = 1
    while True:
        candidate = folder / f"{stem}#{n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def common_parent(paths: list[Path]) -> Path:
    resolved = [p.expanduser().resolve() for p in paths]
    parents = [p if p.is_dir() else p.parent for p in resolved]
    if len(parents) == 1:
        return parents[0]
    parts = list(parents[0].parts)
    for parent in parents[1:]:
        other = list(parent.parts)
        limit = min(len(parts), len(other))
        for i in range(limit):
            if parts[i] != other[i]:
                parts = parts[:i]
                break
        else:
            parts = parts[:limit]
    if not parts:
        return parents[0]
    return Path(*parts)


def slots_for(
    source: Path,
    *,
    output_dir: Path | None,
    consolidate: str | None,
    consolidate_top: Path | None,
) -> Slots:
    source = source.resolve()
    if consolidate_top is not None:
        parent = consolidate_top.parent
        archive = parent / "_archive"
        quarantine = parent / "_quarantine"
        return Slots(consolidate_top, archive, quarantine)

    if consolidate:
        root = source.parent
        output = root / consolidate
        archive = root / "_archive"
        quarantine = root / "_quarantine"
        return Slots(output, archive, quarantine)

    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return Slots(output_dir, None, None)

    return Slots(source.parent, None, None)


def park(source: Path, folder: Path | None) -> Path | None:
    """Move `source` into `folder`, using a #N suffix when the name exists.

    The folder is created here, so `_quarantine` appears only after a real failure.
    Returns the moved path, or None when `folder` is None.
    """
    if folder is None:
        return None
    folder.mkdir(parents=True, exist_ok=True)
    dest = next_free(folder / source.name)
    source.rename(dest)
    provenance.record(dest)
    return dest


def display_dest(dest: Path, source: Path) -> str:
    """Folder/name when the file left the source directory, otherwise just the name."""
    if dest.parent.resolve() == source.resolve().parent:
        return dest.name
    return f"{dest.parent.name}/{dest.name}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def remove_if_empty(path: Path | None, *, ignore_hidden_files: bool = False) -> None:
    """Drop a directory that has no files. Leaves a folder that contains anything.

    With `ignore_hidden_files`, a folder holding only dot files (.DS_Store) counts as empty.
    """
    if path is None or not path.is_dir():
        return
    if ignore_hidden_files:
        leftovers = [p for p in path.iterdir()]
        if all(p.is_file() and p.name.startswith(".") for p in leftovers):
            for p in leftovers:
                p.unlink()
    try:
        next(path.iterdir())
    except StopIteration:
        path.rmdir()


def collect_earlier_runs(
    roots: list[Path],
    *,
    results_dest: Path,
    archive_dest: Path,
    quarantine_dest: Path,
    results_names: set[str],
) -> Counter:
    """Gather what earlier -c runs left under `roots` into the -ct folders, without converting anything again.

    Files in a results folder (_converted, or _ttx for TTX runs) go to `results_dest`, files in `_archive` to
    `archive_dest`, files in `_quarantine` to `quarantine_dest`. The emptied folders are removed. The -ct
    folders themselves are never read from. Returns how many files went to each destination folder.
    """
    dests = {name: results_dest for name in results_names}
    dests["_archive"] = archive_dest
    dests["_quarantine"] = quarantine_dest
    protected = [d.resolve() for d in (results_dest, archive_dest, quarantine_dest)]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for dirpath, dirnames, _ in os.walk(root):
            here = Path(dirpath).resolve()
            if any(here == p or p in here.parents for p in protected):
                dirnames[:] = []
                continue
            if here == root.resolve():
                continue  # the folder you name is the source, never something to gather
            if here.name in dests:
                found.append(here)
                dirnames[:] = []
    moved: Counter = Counter()
    for folder in found:
        dest = dests[folder.name]
        for item in sorted(folder.iterdir()):
            if item.is_file() and not item.name.startswith("."):
                park(item, dest)
                moved[dest.name] += 1
        remove_if_empty(folder, ignore_hidden_files=True)
    return moved
