# Font Catalyst

**Version 1.4.0**

Decompress WOFF and WOFF2 to the TTF or OTF that is already inside them, then report a short structural check. A TTX rebuild is a repair you ask for — not the way a webfont enters the collection.

**Docs:** [Review, flags, and convert](https://andrewsipe.github.io/FontCatalyst/) · also `fontcatalyst --help`

## Install

Preferred: [uv](https://docs.astral.sh/uv/):

```bash
uv tool install "fontcatalyst[otf] @ git+https://github.com/andrewsipe/FontCatalyst.git"
# later: uv tool upgrade fontcatalyst
```

`[otf]` installs skia-pathops and cffsubr, used only by `convert -2 otf`. Overlap removal keeps crossing contours from painting as holes. Subroutinization makes the CFF smaller. If either step cannot run, the conversion still writes the font. The plain install, without `[otf]`, does the refit and skips those two steps. The extra needs Python 3.10+.

From a clone: `uv tool install --editable '.[otf]'` (edits take effect immediately).

Requires Python 3.9+. Formats: TTF, OTF, WOFF, WOFF2 (Brotli is installed with the package).

## Quick start

```bash
# Unwrap webfonts next to the originals and print pass / fail
fontcatalyst fonts/ -r

# Sort into _converted_top/, _archive/, and _quarantine/ (only if something fails)
fontcatalyst fonts/ -r -ct

# Same sort, per source folder (_converted/, _archive/, …)
fontcatalyst fonts/ -r -c

# Apply the one fix the check named (coverage sort, or a TTX rebuild)
fontcatalyst fonts/ -r --repair
```

| Result | Meaning |
|--------|---------|
| **good** | Decompressed (or already SFNT) file kept as-is |
| **questionable** | Kept; note only (e.g. color tables) — not rewritten |
| **bad** | Kept; line names a repair (`structure` / `ttx`) or missing required tables |
| **error** | Could not open or rebuild — fontTools / `ttx` reason on the line |

With `-c` or `-ct`, a successful webfont reports both moves: original → `_archive/…`, and the new TTF or OTF that was written.

## What the check looks at

Opens the file, decompiles tables, checks Coverage / PairPos order, stored checksums, and a short required-table list (`cmap`, `head`, `hhea`, `hmtx`, `maxp`, `name`, `post`, `OS/2`, plus `glyf`/`loca` or `CFF`; `gvar` or `CFF2` when `fvar` is present). It is not Fontspector.

`--repair` runs only the fix the check named. Missing tables are reported and not invented.

## Convert

`convert` is a separate subcommand. `-2` is `--to`. Each run writes one target. There is no all-formats distribution pack.

```bash
fontcatalyst convert -2 woff2 fonts/       # lossless Brotli wrap
fontcatalyst convert -2 woff fonts/        # lossless zlib wrap
fontcatalyst convert -2 otf Family.ttf     # TTF outlines to CFF
```

| `-2` / `--to` | What you get |
|--------|----------------|
| `woff`, `woff2` | The same SFNT, in a new container. Outlines and hints stay. `head.modified` stays the time stored in the source. |
| `otf` | TrueType outlines refit as CFF. TrueType instructions are dropped. Warned every time. |

OTF to TTF is refused. Variable TTF to variable OTF is refused. A file that is already an OTF is skipped, not reported as an error. `-c` / `-ct` sort that one target the same way as the default command.

## TTX

`ttx` the program accepts one file. `fontcatalyst ttx` accepts a directory, and `-r` walks subdirectories, skipping `_archive`, `_quarantine`, and the ttx folders from an earlier run. Each new font is dumped to `.ttx`. If that XML is already there and matches the font, the font stays put and no `#1` file is written. The binary is not rebuilt. That stays on `--repair`, and only when a table will not decompile.

```bash
fontcatalyst ttx fonts/ -r          # Family.ttx beside each font
fontcatalyst ttx fonts/ -r -ct      # .ttx files in _ttx_top/, originals in _archive/
```

## OpenType features

`fontcatalyst otl` audits and repairs a font's GSUB and GPOS features. It was the separate Opentype_Tools package.

```bash
fontcatalyst otl scan fonts/ -r                       # which features exist, what the glyphs could use
fontcatalyst otl connect fonts/ -r --dry-run          # build the FEA that would reconnect them
fontcatalyst otl connect fonts/ -r --apply --backup -y
fontcatalyst otl pipeline fonts/ -r --backup -y       # scan, wrap, connect, aalt, verify, sort
```

| Command | What it does |
|---------|--------------|
| `scan` | Audit installed features, wrap needs, gaps and graded recommendations (`--write-report` adds a family summary) |
| `wrap` | Add OTL scaffolding and enrichment (TrueType and OpenType/CFF) |
| `connect` | Build reconnect FEA; `--apply` merges it into the fonts |
| `aalt` | Build an `aalt` feature from the installed GSUB features |
| `verify` | Read-only health check after the others |
| `sort` | Sort GSUB, GPOS and GDEF Coverage tables (the same fix as `--repair`) |
| `pipeline` | All of them in order; `--no-wrap`, `--no-connect`, `--no-aalt`, `--no-verify`, `--no-sort` skip a step |

Every command takes `-r`, `--dry-run`, `-y`, `--backup` and `--output-dir`. Reports go under `otl_reports/`.

## Related

- [FontFixer](https://github.com/andrewsipe/FontFixer) — OS/2, style, glyph, kern tidy-up  
- [Ebrium](https://github.com/andrewsipe/ebrium) — vertical metrics  
- [Changelog](CHANGELOG.md)
