# Font Catalyst

**Version 1.3.1**

Decompress WOFF and WOFF2 to the TTF or OTF that is already inside them, then report a short structural check. A TTX rebuild is a repair you ask for — not the way a webfont enters the collection.

**Docs:** [Review, flags, and convert](https://andrewsipe.github.io/FontCatalyst/) · also `fontcatalyst --help`

## Install

Preferred: [pipx](https://pipx.pypa.io/):

```bash
pipx install "git+https://github.com/andrewsipe/FontCatalyst.git"
# later: pipx upgrade fontcatalyst
```

Or from a clone: `pipx install .` / `pip install -e .`

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
| `woff`, `woff2` | The same SFNT, in a new container. Outlines and hints stay. The result line says so. |
| `otf` | TrueType outlines refit as CFF. TrueType instructions are dropped. Warned every time. |

OTF to TTF is refused. Variable TTF to variable OTF is refused. `-c` / `-ct` sort that one target the same way as the default command.

## TTX

`ttx` the program accepts one file. `fontcatalyst ttx` accepts a directory, and `-r` walks subdirectories, skipping `_archive`, `_quarantine`, and the ttx folders from an earlier run. Each new font is dumped to `.ttx`. If that XML is already there and matches the font, the font stays put and no `#1` file is written. The binary is not rebuilt. That stays on `--repair`, and only when a table will not decompile.

```bash
fontcatalyst ttx fonts/ -r          # Family.ttx beside each font
fontcatalyst ttx fonts/ -r -ct      # .ttx files in _ttx_top/, originals in _archive/
```

## Related

- [FontFixer](https://github.com/andrewsipe/FontFixer) — OS/2, style, glyph, kern tidy-up  
- [Ebrium](https://github.com/andrewsipe/ebrium) — vertical metrics  
- [Changelog](CHANGELOG.md)
