"""
OpenType Tools library modules.

Shared components for OpenType font manipulation tools.
"""

__all__ = [
    "CONFIG",
    "OperationResult",
    "ResultLevel",
    "ResultMessage",
    "FontValidator",
    "FontState",
    "UnifiedGlyphDetector",
    "GlyphClassification",
    "SSLabeler",
    "WrapperPlan",
    "WrapperStrategyEngine",
    "WrapperExecutor",
    "sort_coverage_tables_in_font",
    "FeatureExtractor",
    "ExistingSubstitutionExtractor",
    "FeatureCodeGenerator",
]

# Import main exports for convenience
from fontcatalyst.opentype.config import CONFIG
from fontcatalyst.opentype.results import (
    OperationResult,
    ResultLevel,
    ResultMessage,
)
from fontcatalyst.opentype.validation import FontValidator, FontState
from fontcatalyst.opentype.detection import (
    UnifiedGlyphDetector,
    GlyphClassification,
)
from fontcatalyst.opentype.ss_labeler import SSLabeler
from fontcatalyst.opentype.wrapper import (
    WrapperPlan,
    WrapperStrategyEngine,
    WrapperExecutor,
)
from fontcatalyst.opentype.coverage import sort_coverage_tables_in_font
from fontcatalyst.opentype.feature_extraction import (
    FeatureExtractor,
    ExistingSubstitutionExtractor,
)
from fontcatalyst.opentype.feature_generation import FeatureCodeGenerator
