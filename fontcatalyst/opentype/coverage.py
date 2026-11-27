"""Coverage sorting for OpenType fonts. The sorter itself lives in FontCore (``core_coverage_sort``); this adds the console output."""

from typing import Tuple

from fontTools.ttLib import TTFont



import FontCore.core_console_styles as cs  # noqa: E402
from FontCore.core_coverage_sort import (  # noqa: E402,F401
    sort_coverage_with_arrays,
    watch_unsorted_coverage,
)
from FontCore.core_coverage_sort import sort_coverage_tables_in_font as _sort  # noqa: E402


def sort_coverage_tables_in_font(font: TTFont, verbose: bool = False) -> Tuple[int, int]:
    """Sort every Coverage table in ``font`` by glyph ID (in place). Returns ``(total, sorted_count)``."""
    report = (lambda line: cs.StatusIndicator("info").add_message(line).emit()) if verbose else None
    return _sort(font, report=report)
