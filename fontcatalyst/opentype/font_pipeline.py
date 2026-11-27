"""The features pipeline, one font at a time.

Each font is opened once. It is audited, then wrapped, connected, given an aalt feature and Coverage-sorted in
memory, checked, and saved once. Every font prints its own block before the next one starts, so a long run shows
what it is doing and a stop part-way leaves the earlier fonts finished.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Dict, List

import FontCore.core_console_styles as cs
from fontTools.ttLib import TTFont

from .aalt_builder import apply_aalt_to_font, build_aalt_plan
from .analyze import analyze_font
from .connect import build_connect_plan, render_connect_fea
from .coverage import sort_coverage_tables_in_font, watch_unsorted_coverage
from .feature_apply import apply_features_to_font, detect_feature_conflicts
from .flow_context import FlowContext
from .io_paths import aalt_fea_path, connect_fea_path
from .models import ConnectOptions
from .utils import atomic_ttfont_save, backup_font
from .validation import FontValidator
from .verify import verify_font
from .wrap_assess import assess_wrap_status
from .wrapper import WrapperExecutor, WrapperStrategyEngine


@dataclass
class Steps:
    wrap: bool = True
    connect: bool = True
    aalt: bool = True
    verify: bool = True
    sort: bool = True


@dataclass
class Tally:
    saved: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: int = 0
    verify_failed: int = 0
    blocked: List[str] = field(default_factory=list)
    # warnings that hit hundreds of fonts, grouped instead of printed under each one: code -> font names
    grouped: Dict[str, List[str]] = field(default_factory=dict)


# structure-note code -> the line the summary prints
GROUPED_WARNINGS = {
    "no-glyph-classes": "font(s) have mark features or mark-filtering lookups but no GDEF glyph classes (marks may not attach)",
    "gsub-unused-lookup": "font(s) have GSUB lookups no feature uses (they do nothing)",
    "gpos-unused-lookup": "font(s) have GPOS lookups no feature uses (they do nothing)",
}


def _line(kind: str, text: str, *, dry: bool = False) -> None:
    ind = cs.StatusIndicator(kind, dry_run=True) if dry else cs.StatusIndicator(kind)
    ind.add_message(text).emit()


def _ask(ctx: FlowContext, name: str, what: str) -> bool:
    """Per-font confirmation unless -y. `a` answers yes for the rest of the run."""
    if ctx.yes:
        return True
    try:
        answer = input(f"  {what} {name}? [y/N/a=all yes]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    if answer in ("a", "all"):
        ctx.yes = True
        return True
    return answer in ("y", "yes")


def _reload(font: TTFont) -> TTFont:
    """Save to memory and read back. A table built in memory (a fresh GDEF, a merged GSUB) lacks fields the
    analysis expects until it has been compiled once, which is what the old step-by-step run got from saving."""
    buf = io.BytesIO()
    font.save(buf)
    font.close()
    buf.seek(0)
    return TTFont(buf, lazy=False)


def _process_font(ctx: FlowContext, font_path, steps: Steps, tally: Tally, options: ConnectOptions) -> None:
    dry = ctx.dry_run
    changes: List[str] = []

    with watch_unsorted_coverage() as watch:
        font = TTFont(font_path, lazy=False)
    try:
        before = verify_font(font, font_path, options=options)
        audit = before.audit
        inv = audit.glyph_inventory
        notes = []
        if audit.otl_stripped_suspected:
            notes.append("OpenType tables look stripped")
        if inv.limited_glyph_set and not inv.has_variant_glyphs:
            notes.append(f"small glyph set ({inv.glyph_count})")
        _line("info", f"{len(audit.existing_tags)} feature(s) installed" + (f"; {', '.join(notes)}" if notes else ""))

        # wrap
        if steps.wrap:
            wrap = audit.wrap_status
            if wrap.flagged_unsupported:
                _line("warning", f"wrap: not supported for this font ({wrap.reason})")
                tally.blocked.append(font_path.name)
            elif wrap.needs_scaffolding:
                engine = WrapperStrategyEngine(font, FontValidator(font))
                plan, plan_result = engine.create_plan({"enrich": True, "skip_validation": False, "overwrite_cmap": False})
                if plan_result.success and plan.has_work():
                    ok, has_changes = WrapperExecutor(font, plan).execute()
                    if ok.success and has_changes:
                        changes.append("wrap")
                        _line("success", "wrap: added OpenType scaffolding", dry=dry)
                        font = _reload(font)
                        audit = analyze_font(font, font_path)
            elif ctx.verbose:
                _line("unchanged", "wrap: not needed")

        # connect (the plan is built from the font as it is now, after any wrap)
        if steps.connect:
            plan = build_connect_plan(audit, options)
            if plan.blocked:
                _line("warning", f"connect: blocked ({plan.block_reason})")
                tally.blocked.append(font_path.name)
            elif plan.has_work:
                fea = render_connect_fea(audit, plan, font)
                fea_path = connect_fea_path(font_path, scan_root=ctx.scan_root, output_dir=ctx.output_dir)
                fea_path.parent.mkdir(parents=True, exist_ok=True)
                fea_path.write_text(fea, encoding="utf-8")
                names = ", ".join(sorted({*plan.features, *plan.stylistic_sets}))
                for msg in detect_feature_conflicts(font, fea):
                    _line("warning", f"connect: {msg}")
                ok, messages = apply_features_to_font(font, fea, replace_mode=False, merge_mode=True)
                if ok:
                    changes.append("connect")
                    font = _reload(font)
                    _line("success", f"connect: {plan.rule_count()} rule(s) for {names}", dry=dry)
                    for msg in messages:
                        if "Skipped contextual" in msg:
                            _line("warning", f"connect: {msg}")
                        elif ctx.verbose:
                            _line("info", f"connect: {msg}")
                else:
                    for msg in messages:
                        _line("error", f"connect: {msg}")
                    raise RuntimeError("connect could not be applied")
            elif ctx.verbose:
                _line("unchanged", "connect: nothing to reconnect")

        # aalt
        if steps.aalt:
            plan = build_aalt_plan(font, force=ctx.aalt_force)
            if plan.blocked:
                _line("warning", f"aalt: skipped. {plan.block_reason}" if ctx.verbose
                      else "aalt: skipped (the features use lookup types aalt cannot reference; `features aalt --force` builds it from the rest; -v says more)")
            elif plan.needs_update:
                aalt_path = aalt_fea_path(font_path, scan_root=ctx.scan_root, output_dir=ctx.output_dir)
                aalt_path.parent.mkdir(parents=True, exist_ok=True)
                aalt_path.write_text(
                    f"# AALT plan for {font_path.name}\n# References: {', '.join(plan.source_tags)}\n\n" + plan.fea_content,
                    encoding="utf-8",
                )
                ok, messages = apply_aalt_to_font(font, force=ctx.aalt_force)
                if ok:
                    changes.append("aalt")
                    font = _reload(font)
                    _line("success", f"aalt: built from {len(plan.source_tags)} feature(s)", dry=dry)
                else:
                    for msg in messages:
                        _line("error", f"aalt: {msg}")
                    raise RuntimeError("aalt could not be applied")
            elif ctx.verbose:
                _line("unchanged", f"aalt: {plan.skip_reason or 'not needed'}")

        # sort
        if steps.sort:
            total, sorted_count = sort_coverage_tables_in_font(font, verbose=False)
            if watch.fired and not sorted_count:
                sorted_count = 1  # out of order in the file, repaired on load: saving writes it sorted
            if sorted_count:
                changes.append("sort")
                _line("success", f"sort: {sorted_count} of {total} Coverage table(s)", dry=dry)
            elif ctx.verbose:
                _line("unchanged", "sort: already in order")

        # verify the result before anything is written
        failed_verify = False
        if steps.verify:
            after = verify_font(font, font_path, options=options)
            new_errors = len(after.errors) - len(before.errors)
            for finding in after.errors:
                _line("error", f"verify: {finding.message}")
            for finding in after.warnings:
                if finding.code in GROUPED_WARNINGS:
                    tally.grouped.setdefault(finding.code, []).append(font_path.name)
                elif ctx.verbose:
                    _line("warning", f"verify: {finding.message}")
            if after.errors:
                failed_verify = True
                tally.verify_failed += 1
            if changes and new_errors > 0:
                _line("error", "not saved: the changes introduced verify errors")
                tally.errors += 1
                return

        if not changes:
            _line("unchanged", "no changes")
            tally.unchanged += 1
            return
        if dry:
            _line("preview", f"would save ({', '.join(changes)})", dry=True)
            tally.saved += 1
            return
        if not _ask(ctx, font_path.name, "Save"):
            _line("skipped", "not saved")
            tally.skipped += 1
            return
        if ctx.backup:
            backup_font(font_path)
        atomic_ttfont_save(font, font_path)
        _line("saved", f"saved ({', '.join(changes)})")
        tally.saved += 1
    finally:
        font.close()


def run_pipeline(ctx: FlowContext, steps: Steps) -> int:
    fonts = ctx.resolved_fonts()
    options = ConnectOptions(include_low=ctx.connect_include_low, include_manual=ctx.connect_include_manual)
    tally = Tally()
    total = len(fonts)
    for i, font_path in enumerate(fonts, 1):
        cs.emit("")
        _line("parsing", f"[{i}/{total}] {font_path.name}")
        try:
            _process_font(ctx, font_path, steps, tally, options)
        except Exception as e:  # one bad font must not stop the run
            _line("error", f"{font_path.name}: {e}")
            tally.errors += 1

    cs.emit("")
    label = "Pipeline preview complete" if ctx.dry_run else "Pipeline complete"
    cs.StatusIndicator("success").add_message(label).with_summary_block(
        updated=tally.saved, unchanged=tally.unchanged + tally.skipped, errors=tally.errors
    ).emit()
    if tally.blocked:
        _line("warning", f"{len(tally.blocked)} font(s) blocked from wrap or connect (see messages above)")
    for code, names in tally.grouped.items():
        shown = ", ".join(names[:5]) + (f" and {len(names) - 5} more" if len(names) > 5 else "")
        _line("warning", f"{len(names)} {GROUPED_WARNINGS[code]}: {shown}")
    if tally.verify_failed:
        _line("error", f"verify found errors in {tally.verify_failed} font(s)")
    return 0 if tally.errors == 0 and tally.verify_failed == 0 else 1
