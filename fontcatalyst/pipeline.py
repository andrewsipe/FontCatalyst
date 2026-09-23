"""Decompress, review, repair, and limited conversion."""

from __future__ import annotations

from pathlib import Path

from dataclasses import dataclass

import FontCore.core_console_styles as cs

from fontcatalyst.convert import ConvertError, ttf_to_otf, wrap
from fontcatalyst.folders import Slots, display_dest, ensure_dir, next_free, park
from fontcatalyst.repair import apply_structure, dump_ttx, rebuild_with_ttx
from fontcatalyst.review import checksums_fail, review_font
from fontcatalyst.sfnt import (
    WEB_EXTENSIONS,
    decompress,
    is_cff,
    load_font,
    outline_label,
    sfnt_suffix,
)


@dataclass
class Outcome:
    status: str
    name: str
    level: str
    detail: str
    archived: str | None = None
    written: str | None = None
    quarantined: str | None = None


def ingest_file(path: Path, slots: Slots, repair: bool) -> Outcome:
    checksum = checksums_fail(path)
    checksum_note = None
    if checksum:
        checksum_note = f"Stored checksums do not match ({checksum})."

    try:
        font = load_font(path)
    except Exception as exc:
        quarantined = park(path, slots.quarantine)
        where = display_dest(quarantined, path) if quarantined else None
        return Outcome(
            "error",
            path.name,
            "error",
            f"{type(exc).__name__}: {exc}",
            quarantined=where,
        )

    web = path.suffix.lower() in WEB_EXTENSIONS
    try:
        if web:
            decompress(font)
        result = review_font(font, None if web else checksum_note)
        if web and checksum_note:
            result.lines.append(
                checksum_note + " Writing the SFNT recalculates them."
            )
            if result.level == "good":
                result.level = "questionable"

        wrote_new = False
        if repair and result.repair == "structure":
            apply_structure(font)
            result.lines.append("Sorted coverage tables and PairPos records.")
            wrote_new = True
        elif repair and result.repair == "ttx":
            font = rebuild_with_ttx(font)
            result.lines.append("Rebuilt the font through TTX.")
            wrote_new = True

        archived = None
        written = None
        if web or wrote_new:
            ensure_dir(slots.output)
            dest = next_free(slots.output / f"{path.stem}{sfnt_suffix(font)}")
            decompress(font)
            font.save(dest)
            written = display_dest(dest, path)
            archived_path = park(path, slots.archive)
            if archived_path is not None:
                archived = display_dest(archived_path, path)
        elif slots.archive is not None and result.passed:
            park(path, slots.output)

        status = "pass" if result.passed else "fail"
        extra = ""
        if result.repair and not (repair and wrote_new):
            status = "fail"
            extra = f" Recommend --repair ({result.repair})."
        elif result.repair and wrote_new:
            status = "pass"
        detail = (" ".join(result.lines) + extra).strip()
        return Outcome(status, path.name, result.level, detail, archived, written)
    except Exception as exc:
        quarantined = park(path, slots.quarantine)
        where = display_dest(quarantined, path) if quarantined else None
        return Outcome(
            "error", path.name, "error", f"{type(exc).__name__}: {exc}", quarantined=where
        )
    finally:
        font.close()


def ttx_file(path: Path, slots: Slots) -> Outcome:
    """Dump one font to TTX XML. The binary is left as the source file."""
    try:
        ensure_dir(slots.output)
        dest = next_free(slots.output / f"{path.stem}.ttx")
        try:
            dump_ttx(path, dest)
        except Exception:
            if dest.exists():
                dest.unlink()
            raise
        written = display_dest(dest, path)
        archived_path = park(path, slots.archive)
        archived = display_dest(archived_path, path) if archived_path else None
        return Outcome(
            "pass",
            path.name,
            "good",
            "Dumped the font to TTX. The binary was not rebuilt.",
            archived,
            written,
        )
    except Exception as exc:
        quarantined = park(path, slots.quarantine)
        where = display_dest(quarantined, path) if quarantined else None
        return Outcome(
            "error", path.name, "error", f"{type(exc).__name__}: {exc}", quarantined=where
        )


def convert_file(path: Path, slots: Slots, target: str) -> Outcome:
    """Wrap to woff/woff2, or convert TTF outlines to CFF (.otf)."""
    if target == "ttf":
        return Outcome(
            "error",
            path.name,
            "error",
            "OTF to TTF approximates cubics and drops CFF hints. It is not offered.",
        )
    try:
        font = load_font(path)
    except Exception as exc:
        quarantined = park(path, slots.quarantine)
        where = display_dest(quarantined, path) if quarantined else None
        return Outcome(
            "error", path.name, "error", f"{type(exc).__name__}: {exc}", quarantined=where
        )

    try:
        if target in {"woff", "woff2"}:
            notes = wrap(font, target)
            suffix = f".{target}"
        elif target == "otf":
            if is_cff(font):
                raise ConvertError(
                    f"Already {outline_label(font)}. -2 otf refits TrueType outlines only."
                )
            notes = ttf_to_otf(font)
            suffix = ".otf"
        else:
            raise ConvertError(f"Unknown target {target!r}.")

        ensure_dir(slots.output)
        dest = next_free(slots.output / f"{path.stem}{suffix}")
        font.save(dest)
        written = display_dest(dest, path)
        archived_path = park(path, slots.archive)
        archived = display_dest(archived_path, path) if archived_path else None
        detail = " ".join(notes)
        return Outcome("pass", path.name, "good", detail, archived, written)
    except ConvertError as exc:
        return Outcome("error", path.name, "error", str(exc))
    except Exception as exc:
        quarantined = park(path, slots.quarantine)
        where = display_dest(quarantined, path) if quarantined else None
        return Outcome(
            "error", path.name, "error", f"{type(exc).__name__}: {exc}", quarantined=where
        )
    finally:
        font.close()


_LEVEL_STYLE = {
    "good": "bold green",
    "questionable": "bold dark_orange",
    "bad": "bold red",
    "error": "bold red",
}


def _escape_markup(text: str) -> str:
    return text.replace("[", "\\[")


def emit(status: str, message: str) -> None:
    console = cs.get_console()
    kind = {"pass": "success", "fail": "warning", "error": "error"}.get(status, "info")
    cs.StatusIndicator(kind).add_message(message).emit(console)


def emit_outcome(outcome: Outcome) -> None:
    """Show where a webfont went, then the file that was written and its level."""
    console = cs.get_console()
    if outcome.archived:
        cs.StatusIndicator("updated").add_message(
            cs.fmt_change(outcome.name, outcome.archived)
        ).emit(console)
    if outcome.quarantined:
        cs.StatusIndicator("error").add_message(
            cs.fmt_change(outcome.name, outcome.quarantined)
        ).with_explanation(_escape_markup(outcome.detail)).emit(console)
        return
    if outcome.written and outcome.archived:
        _emit_level(outcome, subject=outcome.written, console=console)
        return
    if outcome.written:
        _emit_level(
            outcome,
            subject=cs.fmt_change(outcome.name, outcome.written),
            console=console,
            subject_is_markup=True,
        )
        return
    _emit_level(outcome, subject=_escape_markup(outcome.name) + ":", console=console)


def _badge(outcome: Outcome) -> str:
    if outcome.level == "questionable":
        return "warning"
    if outcome.status == "pass":
        return "success"
    return "error"


def _emit_level(
    outcome: Outcome,
    subject: str,
    console,
    subject_is_markup: bool = False,
) -> None:
    badge = _badge(outcome)
    style = _LEVEL_STYLE.get(outcome.level, "bold")
    safe_detail = _escape_markup(outcome.detail)
    shown = subject if subject_is_markup else _escape_markup(subject)
    if badge == "error":
        # The error template already inserts ": " before the explanation.
        label = shown[:-1] if shown.endswith(":") else shown
        line = cs.StatusIndicator(badge).add_message(label)
        line.explanation = f"[{style}]{outcome.level}.[/] [dim]{safe_detail}[/]"
    else:
        line = (
            cs.StatusIndicator(badge)
            .add_message(shown)
            .add_message(f"{outcome.level}.", style=style)
        )
        if safe_detail:
            line.add_message(safe_detail, style="dim")
    line.emit(console)
