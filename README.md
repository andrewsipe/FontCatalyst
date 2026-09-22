# Font Catalyst

**Version 1.1.6**

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

## Conversion (limited)

```bash
fontcatalyst convert --to woff2 fonts/
fontcatalyst convert --to woff fonts/
fontcatalyst convert --to otf Family.ttf
```

`--to otf` refits TrueType outlines as CFF and drops TrueType instructions — warned every time. OTF to TTF and variable outline conversion are refused.

## Related

- [FontFixer](https://github.com/andrewsipe/FontFixer) — OS/2, style, glyph, kern tidy-up  
- [ebrium](https://github.com/andrewsipe/ebrium) — vertical metrics  
- [Changelog](CHANGELOG.md)
