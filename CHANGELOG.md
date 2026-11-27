# Changelog

## [1.8.0] - 2026-11-27

### Added
- Character variants: glyphs named `base.cv01` to `base.cv99` are detected, shown in `scan` next to the stylistic sets, and written into the `connect` plan as `cvNN` features. The variant needs its base glyph in the font.
- Stylistic-set glyph names are matched with one or two digits and any case (`a.ss7`, `b.SS03`).

### Changed (pipeline)
- `features pipeline` now works one font at a time: read once, audit, wrap, connect, aalt, sort, verify, save once, then the next font. Each font prints its own block. A font is not saved if the changes add verify errors. The separate `scan`, `wrap`, `connect`, `aalt`, `sort` and `verify` commands are unchanged.

### Fixed
- `connect` gave a different plan on identical runs: glyphs were visited in set order, which changes with Python's hash seed. They are now read in the font's own order, so the same font always gives the same plan.
- `liga` no longer picks up stylistic variants of a ligature (`fl.ss07`, `fi.ss07.ss05`). Before, `connect` could write `sub f l by fl.ss07;` into liga. Only `fi` or `fi.liga`-style names count, and the plain name wins when both exist.
- `connect` failed with "can only concatenate list (not tuple) to list" on fonts with ligatures (UniversalSansDisplay Custom Variable Italic); fixed in the existing-ligature reader and in wrap.
- `features pipeline`, `scan` and `verify` showed nothing while they read the fonts, which on a few thousand fonts looked like a hang. They now show a progress bar with the count and the current font, and the pipeline prints "Step N of M" before each step.

### Changed
- `features` help now matches the other commands: a "Heads up" panel, examples, notes and exit status, with the same input / run / output / general groups on every subcommand.
- `features --output-dir` is now `--report-dir`, since it only moves the `otl_reports` folders. `--output-dir` still works. `-n` is a short form of `--dry-run`.
- `--backup` is no longer offered on `scan` and `verify`, which never change fonts.
- `fontcatalyst otl` is now `fontcatalyst features`. `otl` still works as an alias.

### Removed
- `-j/--jobs` on the default command, `convert` and `ttx`. It never did anything.

## [1.7.0] - 2026-11-27

### Added
- `fontcatalyst otl`: the OpenType feature tools (scan, wrap, connect, aalt, verify, sort, pipeline) now live here instead of in the separate Opentype_Tools package. The commands, options and `otl_reports/` output are unchanged; the old `report` alias is dropped (use `scan --write-report`).

## [1.6.1] - 2026-11-27

FontCore 0.12.0 vendored (see `FontCore/VENDOR.md`).

### Fixed
- The check now flags a font whose file holds an out-of-order Coverage table. fontTools repairs that quirk as it reads, so the check used to see a sorted font and call it good while the warning kept coming back. `--repair` writes it sorted.
- The coverage sort moves the arrays that run parallel to a Coverage (mark and base anchors, rule sets, single-position values, cursive entries, GDEF attach points) with it. It used to move only pair sets, so a sort could give a glyph its neighbour's anchors.

### Changed
- The coverage sorter is FontCore's `core_coverage_sort`, shared with the OpenType tools. This tool no longer carries its own copy.

## [1.6.0] - 2026-11-25

### Changed
- A font is skipped as "from an earlier run" because this tool wrote or moved it, not because of its folder's name. Each folder the tool puts fonts in gets a hidden `.fontcatalyst.json` (name, size, SHA-256). A font you drop into `_converted` later, or one edited since, is processed; fonts the tool wrote into a folder with any other name (`-o web_ready`) are skipped. Folders from older runs have no manifest and are still recognised by name.
- Fonts directly in a folder you name, and fonts you name yourself, are always processed (unchanged).

## [1.5.0] - 2026-11-25

FontCore 0.8.2 vendored (see `FontCore/VENDOR.md`).

### Changed
- A run ends with one sentence ("Converted 3, skipped 1, 2 problems."), and a warning chip when anything went wrong.
- The exit code is 1 when any font failed or errored (it was always 0).

## [1.4.0] - 2026-11-25

FontCore 0.7.0 vendored (see `FontCore/VENDOR.md`). Its file collector now skips macOS junk and hidden files and folders, lists each real file once, and warns about a path that does not exist.

### Fixed
- `-ct` on a folder that is itself an earlier-run folder (for example `fontcatalyst -ct -r PATH/_converted`) gathered that folder's own files into a `_converted_top` inside it and then crashed with a `FileNotFoundError` traceback. The folder you name is now always the source, never something to gather, and only earlier-run folders below it are gathered. A file that disappears mid-run (or any per-file error) is now an error line and the run continues, with the error counted in the summary.

### Added
- `-ct` now gathers what an earlier `-c` run left behind, so `-c -r` followed by `-ct -r` brings everything to one top-level folder without converting anything twice. Fonts in the per-folder `_converted` folders (or `_ttx` for `ttx`) move into the `-ct` results folder (`_converted_top` / `_ttx_top`), `_archive` into the top `_archive`, and `_quarantine` into the top `_quarantine`; names that already exist get a `#1` suffix as before, and the emptied folders are removed. New files in the same tree are converted in the same run. A second `-ct` pass changes nothing. `-c` alone still skips earlier-run folders.
- `--include-generated`: also process fonts inside earlier-run folders (the `_archive` originals are converted again, so this is rarely what you want after a `-c` run; use `-ct`).

### Changed
- When every font found sits inside folders from an earlier run and nothing is gathered, FontCatalyst says so and names the folders (instead of "No TTF, OTF, WOFF, or WOFF2 files found"), and points to `-ct`. When only some are skipped, it says how many.

## [Unreleased]

### Changed
- Install and update instructions use `uv tool install` / `uv tool upgrade` (pipx is no longer mentioned).

## [1.3.9] - 2026-11-22

### Changed
- Vendored FontCore refreshed to v0.4.0. The modules this tool uses are byte-for-byte the same as in 0.3.1, so nothing changes in behavior; only the version stamp in `FontCore/VENDOR.md` moves.

## [1.3.8] - 2026-11-21

### Fixed
- Vendored FontCore is stamped as 0.3.1 (the 0.3.0 copy was labeled 0.2.4 in `FontCore/VENDOR.md`). No change to what the tool does.

## [1.3.7] - 2026-11-21

### Changed
- Vendored FontCore refreshed to v0.3.0 (console wording and counts: "1 file" / "3 files", `Finished`, one `Proceed?`). No change to what the tool does to fonts.

## [1.3.6] - 2026-11-20

### Changed
- Vendored FontCore refreshed to v0.2.0 (see `FontCore/VENDOR.md`). A filename
  containing square brackets is no longer read as a console style tag.
- The vendored copy is now produced by FontCore's `tools/vendor_fontcore.py`,
  with the module list declared under `[tool.fontcore-vendor]` in `pyproject.toml`.

## [1.3.5] - 2026-09-30

### Changed
- Saves keep `head.modified` at the time stored in the source font.
  `head.checkSumAdjustment` is still recalculated.

## [1.3.4] - 2026-09-30

### Fixed
- A folder you pass directly is processed even when its name is `_converted`,
  `_archive`, `_ttx`, or another output name. Those names are still skipped
  when `-r` finds them nested under a broader folder.

## [1.3.3] - 2026-09-30

### Added
- The `otf` extra installs skia-pathops and cffsubr for `convert -2 otf`.
  Overlap removal and CFF subroutinization run when those packages are present.
  A contour that overlap removal leaves without an on-curve point is given an
  explicit one before the cubic refit, so that case still converts.
  A failure in either step is undone, and the conversion still writes the font.

## [1.3.2] - 2026-09-30

### Changed
- A font that is already the convert target (an OTF asked for `--to otf`, or a
  webfont already in the requested flavor) is skipped. The file stays put, and
  the line is not an error.

## [1.3.1] - 2026-09-22

### Changed
- `fontcatalyst ttx` leaves a font alone when the `.ttx` it would write already
  matches that font. It does not add a `#1` copy or rename the binary.
- `-r` does not walk `_archive`, `_quarantine`, or the ttx output folders.
  A repeat that finds only those folders names them, then says no fonts were found.
- `ttx` is invoked with `--no-recalc-timestamp`, so `head.modified` stays the
  time stored in the font.

## [1.3.0] - 2026-09-22

### Added
- `fontcatalyst ttx` dumps a file or a directory tree to TTX. `-r` walks
  subdirectories. The binary font is not rebuilt.
- `-c` / `-ct` on that command default to `_ttx` and `_ttx_top`.

## [1.2.1] - 2026-09-22

### Added
- `convert -2` is the short form of `convert --to`.

## [1.2.0] - 2026-09-22

### Changed
- `convert` is documented and helped as its own subcommand (`fontcatalyst convert --help`),
  with a target table for what `--to` does.
- WOFF and WOFF2 wraps print a clarification: the container changed, outlines and hints did not.
  A file that is already that flavor is left in place.
- A variable font wrapped as WOFF notes that WOFF2 is the usual container.
- No all-formats distribution pack. Each convert run writes one target.

## [1.1.6] - 2026-09-22

### Fixed
- `fontcatalyst convert --version` now works (version was only on the top-level parser).
- Shared flags land in named groups (`input`, `output and sorting`) instead of a bare
  unlabeled options bucket; `--to` has its own `conversion target` group.
- Exit-status help text: exit 1 is only “no matching files found” — per-file refusals
  stay as error outcomes and still exit 0.

## [1.1.5] - 2026-09-22

### Added
- GitHub Pages docs site and pipx install from the public repository.

### Changed
- README and `--help` docs hint point at
  https://andrewsipe.github.io/FontCatalyst/

## [1.1.4] - 2026-09-22

### Changed
- Decompressing a webfont reports both moves: the original into `_archive`
  (with `-c` or `-ct`) and the TTF or OTF that was written.

## [1.1.3] - 2026-09-22

### Changed
- Result lines color the level word: green good, orange questionable, red bad
  or error. The rest of the line is dim so the level is easy to scan.

## [1.1.2] - 2026-09-22

### Added
- The structural check fails when a required table is missing (`cmap`, `head`,
  `hhea`, `hmtx`, `maxp`, `name`, `post`, `OS/2`, plus `glyf`/`loca` or `CFF`,
  and `gvar` or `CFF2` when `fvar` is present). Nothing is rewritten; `--repair`
  is not offered for that case.

## [1.1.1] - 2026-09-22

### Changed
- `-c` / `-ct` create `_quarantine` only when a file fails. An empty one left
  from a previous run is removed at the end of the next run.

## [1.1.0] - 2026-09-22

### Changed
- The default command decompresses WOFF/WOFF2 to the embedded TTF or OTF and
  prints a structural review. It no longer round-trips every font through TTX.
- `-c` / `-ct` still empty the source folder: results, `_archive` (originals),
  and `_quarantine` (hard failures, with the reason on the error line).
- `--repair` applies only the fix the check named: coverage / PairPos sort, or
  a TTX rebuild when a table will not decompile.

### Added
- `fontcatalyst convert --to woff|woff2|otf`. TTF to OTF warns that outlines
  are refit and TrueType hinting is dropped. OTF to TTF is refused.

## [1.0.0] - 2026-09-22

### Added
- **Font Catalyst** package (`fontcatalyst` CLI) — formerly TTX_Converter
- Vendored slim FontCore + in-package Coverage / PairPos pre-sort
- Rich `--help` with safety panel; local docs under `docs/`
- `pyproject.toml` for pipx / pip install from this folder
