"""Output folders for the default run and for -c / -ct."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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
    return dest


def display_dest(dest: Path, source: Path) -> str:
    """Folder/name when the file left the source directory, otherwise just the name."""
    if dest.parent.resolve() == source.resolve().parent:
        return dest.name
    return f"{dest.parent.name}/{dest.name}"


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def remove_if_empty(path: Path | None) -> None:
    """Drop a directory that has no files. Leaves a folder that contains anything."""
    if path is None or not path.is_dir():
        return
    try:
        next(path.iterdir())
    except StopIteration:
        path.rmdir()
