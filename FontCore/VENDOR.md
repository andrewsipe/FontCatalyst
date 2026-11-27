# Vendored FontCore subset

fontcatalyst ships a minimal copy of [FontCore](https://github.com/andrewsipe/FontCore)
so it installs without the full library, a submodule, or a symlink.

**Source:** FontCore 0.12.0 (`v0.11.6-7-gc709070`)

**Do not edit these files here.** Fix them in FontCore, then re-sync.

## Declared modules

- `core_cli_help.py`
- `core_coverage_sort.py`
- `core_console_config.py`
- `core_console_styles.py`
- `core_file_collector.py`
- `core_logging_config.py`

## Pulled in as imports of the above

- `core_gpos_repair.py`

## Refresh

From a FontCore checkout:

```bash
python tools/vendor_fontcore.py sync ../fontcatalyst
```

The module list lives in `[tool.fontcore-vendor]` in this project's `pyproject.toml`.
