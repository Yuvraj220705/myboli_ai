"""Sprint 3.0.2: Strategy Configuration for Maayboli AI Response Strategy Engine.

Provides centralized, configurable settings for response policies, strategy names,
confidence thresholds, and default prompt versions without hardcoded magic values.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any


class ResponsePolicy(str, Enum):
    """Supported response policies for controlling answer strictness and extra guidance."""
    STRICT = "STRICT"
    BALANCED = "BALANCED"
    HELPFUL = "HELPFUL"


class StrategyName(str, Enum):
    """Supported response strategy identifiers."""
    LATEST_NEWS = "LATEST_NEWS"
    PERSON_SUMMARY = "PERSON_SUMMARY"
    DISTRICT_SUMMARY = "DISTRICT_SUMMARY"
    TOPIC_SUMMARY = "TOPIC_SUMMARY"
    MULTI_ARTICLE_SUMMARY = "MULTI_ARTICLE_SUMMARY"
    ENTITY_COMPARISON = "ENTITY_COMPARISON"
    TIMELINE_RESPONSE = "TIMELINE_RESPONSE"
    PARTIAL_INFORMATION = "PARTIAL_INFORMATION"
    RELATED_INFORMATION = "RELATED_INFORMATION"
    NO_INFORMATION = "NO_INFORMATION"


# Confidence Thresholds
DEFAULT_HIGH_CONFIDENCE_THRESHOLD: float = 80.0
DEFAULT_MEDIUM_CONFIDENCE_THRESHOLD: float = 50.0


@dataclass
class StrategyConfig:
    """Configurable parameters for the Response Strategy Engine."""
    default_policy: ResponsePolicy = ResponsePolicy.BALANCED
    default_prompt_version: str = "v1.0"
    high_confidence_threshold: float = DEFAULT_HIGH_CONFIDENCE_THRESHOLD
    medium_confidence_threshold: float = DEFAULT_MEDIUM_CONFIDENCE_THRESHOLD
    polite_fallback_msg: str = "माझ्याकडे या विशिष्ट विषयासंबंधी प्रकाशित माहिती उपलब्ध नाही."
    
    # Custom strategy mapping overrides (extensibility hook)
    custom_strategy_mappings: Dict[str, str] = field(default_factory=dict)


__all__ = [
    "ResponsePolicy",
    "StrategyName",
    "DEFAULT_HIGH_CONFIDENCE_THRESHOLD",
    "DEFAULT_MEDIUM_CONFIDENCE_THRESHOLD",
    "StrategyConfig",
]
