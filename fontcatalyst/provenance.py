"""Which fonts this tool wrote or moved, so a later run does not take its own output for new work.

Each folder the tool puts a font in gets a hidden `.fontcatalyst.json` listing those fonts with their size and
SHA-256. A font counts as "ours" only while it is unchanged: a font the user drops in later, or one edited since, is
new work. Folders from before this file existed have no manifest, and the caller falls back to the folder name.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

MANIFEST = ".fontcatalyst.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load(folder: Path) -> dict:
    try:
        data = json.loads((folder / MANIFEST).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def has_manifest(folder: Path) -> bool:
    return (folder / MANIFEST).is_file()


def record(path: Path) -> None:
    """Note that this tool put `path` where it is. Never raises: a read-only folder just goes unrecorded."""
    try:
        entries = _load(path.parent)
        entries[path.name] = {"size": path.stat().st_size, "sha256": _sha256(path)}
        tmp = path.parent / (MANIFEST + ".tmp")
        tmp.write_text(json.dumps(entries, indent=1, sort_keys=True), encoding="utf-8")
        os.replace(tmp, path.parent / MANIFEST)
    except OSError:
        pass


def is_ours(path: Path) -> bool:
    """True when this tool wrote or moved `path` and it has not changed since."""
    entry = _load(path.parent).get(path.name)
    if not entry:
        return False
    try:
        return path.stat().st_size == entry.get("size") and _sha256(path) == entry.get("sha256")
    except OSError:
        return False
