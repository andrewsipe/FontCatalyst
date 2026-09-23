# Product notes — Font Catalyst

## Shipped (1.2.0)

Default path is decompress + review. TTX is `--repair` when a table will not decompile.
`-c` / `-ct` sort into converted, `_archive`, and `_quarantine` (quarantine only on failure).

`convert` is a subcommand with one target per run (`--to woff|woff2|otf`).
WOFF/WOFF2 are lossless container wraps and say so. TTF to OTF prints the fidelity warning
(qu2cu, overlap removal, CFF). OTF to TTF and variable outline conversion are refused.
The all-formats distribution pack (labeled folders of every flavor) is out of scope.

GitHub: https://github.com/andrewsipe/FontCatalyst  
Pages: https://andrewsipe.github.io/FontCatalyst/

## Deferred

- Parallel `-j` (flag is accepted; files still run in order)
- Optional `otfautohint` after TTF to OTF
- Zopfli WOFF
- Fontspector as an optional deeper report
- OS/2 upgrades and CFF→CFF2 (leave to FontFixer / other tools)
