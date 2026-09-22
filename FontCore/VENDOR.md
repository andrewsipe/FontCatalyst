# Vendored FontCore subset — Font Catalyst

Copied from the monorepo `FontCore/` for a self-contained install.
Refresh by re-copying these modules from the main FontCore tree.

## Included

| Module | Role |
|--------|------|
| `core_console_styles` | Rich StatusIndicator / progress |
| `core_console_config` | Style tokens (import of styles) |
| `core_logging_config` | Logger used by console config |
| `core_file_collector` | `iter_font_files` |
| `core_cli_help` | Rich `--help` building blocks |

Coverage / GPOS pre-sort lives in `fontcatalyst/coverage_sort.py` (not FontCore).
