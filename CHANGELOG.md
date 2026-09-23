# Changelog

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
