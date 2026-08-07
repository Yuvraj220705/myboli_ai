"""Sprint 3.0.2: Response Strategy Engine for Maayboli AI.

Acts as the decision-making brain between Intent Validation and Answer Generation.
Deterministically decides WHICH response strategy to execute based on user intent,
retrieval status, match confidence, and configurable response policies.

Single Responsibility:
Decide the response strategy and policy flags.
Does NOT perform retrieval, query rewriting, context modification, prompt assembly, or Gemini model calls.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Set

from query_processor import QueryInfo
from intent_validator import IntentValidationResult
from strategy_config import (
    ResponsePolicy,
    StrategyConfig,
    StrategyName,
)

logger = logging.getLogger(__name__)

__all__ = [
    "ResponseStrategy",
    "ResponseStrategyEngine",
]


@dataclass
class ResponseStrategy:
    """Reusable object representing the determined answer response strategy.

    Attributes:
        strategy_name: Name of the selected response strategy.
        response_policy: Active response policy ("STRICT", "BALANCED", "HELPFUL").
        confidence_level: Match confidence level ("HIGH", "MEDIUM", "LOW").
        requires_related_news: Flag indicating if related news should be appended.
        requires_missing_information_notice: Flag indicating if missing info notice is needed.
        requires_fallback: Flag indicating if polite fallback response is required.
        requires_multi_section_output: Flag indicating if answer should be split into sections.
        recommended_prompt_version: Recommended prompt template version.
        internal_reason: Internal explanation for logging and auditability.
    """
    strategy_name: str
    response_policy: str
    confidence_level: str
    requires_related_news: bool
    requires_missing_information_notice: bool
    requires_fallback: bool
    requires_multi_section_output: bool
    recommended_prompt_version: str
    internal_reason: str

    def to_dict(self) -> Dict[str, Any]:
        """Convert strategy object to dictionary for logging and serialization."""
        return {
            "strategy_name": self.strategy_name,
            "response_policy": self.response_policy,
            "confidence_level": self.confidence_level,
            "requires_related_news": self.requires_related_news,
            "requires_missing_information_notice": self.requires_missing_information_notice,
            "requires_fallback": self.requires_fallback,
            "requires_multi_section_output": self.requires_multi_section_output,
            "recommended_prompt_version": self.recommended_prompt_version,
            "internal_reason": self.internal_reason,
        }


class ResponseStrategyEngine:
    """Deterministic engine selecting appropriate response strategy and flags."""

    def __init__(self, config: Optional[StrategyConfig] = None):
        """Initialize ResponseStrategyEngine with optional custom configuration.

        Args:
            config: Optional StrategyConfig object. Uses defaults if None.
        """
        self.config = config or StrategyConfig()

    def select_strategy(
        self,
        query_info: QueryInfo,
        context_pkg: Any,
        validation_result: Optional[IntentValidationResult] = None,
        policy: Optional[str] = None,
    ) -> ResponseStrategy:
        """Deterministically select response strategy based on query intent, context, and validation quality.

        Args:
            query_info: QueryInfo object from QueryProcessor.
            context_pkg: ContextPackage object from ContextBuilder.
            validation_result: Optional IntentValidationResult object from IntentValidator.
            policy: Optional explicit policy string ("STRICT", "BALANCED", "HELPFUL").

        Returns:
            ResponseStrategy detailing selected strategy, flags, and internal explanation.
        """
        active_policy = (policy or self.config.default_policy).upper()
        if active_policy not in [p.value for p in ResponsePolicy]:
            logger.warning("Unknown response policy '%s'. Falling back to DEFAULT (%s)", active_policy, self.config.default_policy)
            active_policy = self.config.default_policy

        # Extract articles and validation metrics
        articles = getattr(context_pkg, "articles", []) if context_pkg else []
        article_count = len(articles)

        match_status = getattr(validation_result, "retrieval_status", "NO_MATCH") if validation_result else ("EXACT_MATCH" if article_count > 0 else "NO_MATCH")
        confidence_level = getattr(validation_result, "confidence", "LOW") if validation_result else ("HIGH" if article_count > 0 else "LOW")
        overall_score = getattr(validation_result, "overall_match_score", 0.0) if validation_result else (100.0 if article_count > 0 else 0.0)

        # -------------------------------------------------------------
        # 1. Deterministic Strategy Selection Rules
        # -------------------------------------------------------------
        if not articles or match_status == "NO_MATCH":
            strategy_name = StrategyName.NO_INFORMATION
            internal_reason = "No matching published articles retrieved in context."

        elif match_status == "RELATED_MATCH":
            strategy_name = StrategyName.RELATED_INFORMATION
            internal_reason = f"Context contains related news, but missing target topics: {', '.join(getattr(validation_result, 'missing_topics', []))}"

        elif match_status == "PARTIAL_MATCH":
            strategy_name = StrategyName.PARTIAL_INFORMATION
            internal_reason = f"Context partially satisfies intent; missing specific topics/entities: {', '.join(getattr(validation_result, 'missing_topics', []))}"

        else:
            # EXACT_MATCH: Determine fine-grained structural strategy based on QueryInfo & context
            raw_q = query_info.original_query if query_info else ""
            clean_q = query_info.clean_query if query_info else ""

            is_latest = getattr(query_info, "latest_news", False) or any(k in raw_q for k in ["ताज्या", "ताजी", "नुकत्याच", "आजच्या", "आज काय"])
            has_date = getattr(query_info, "date", None) is not None or any(k in raw_q for k in ["कालच्या", "वेळापत्रक", "इतिहास", "घटनाक्रम"])
            
            # Check for multiple entities (Person/District) or comparison intent
            matched_people = self._extract_people_from_query_info(query_info, validation_result)
            matched_districts = self._extract_districts_from_query_info(query_info, validation_result)
            is_comparison = len(matched_people) > 1 or len(matched_districts) > 1 or any(k in raw_q for k in ["विरुद्ध", "तुलना", "आणि", "अन्"]) and (len(matched_people) + len(matched_districts) > 1)

            if is_comparison:
                strategy_name = StrategyName.ENTITY_COMPARISON
                internal_reason = f"Multi-entity query detected (People: {matched_people}, Districts: {matched_districts}). Executing comparative response strategy."

            elif is_latest:
                strategy_name = StrategyName.LATEST_NEWS
                internal_reason = "Latest news intent detected. Formatting response as recent developments list."

            elif has_date:
                strategy_name = StrategyName.TIMELINE_RESPONSE
                internal_reason = "Temporal or timeline intent detected. Structuring response in chronological order."

            elif len(matched_people) == 1:
                strategy_name = StrategyName.PERSON_SUMMARY
                internal_reason = f"Person entity '{matched_people[0]}' detected. Generating focused person summary response."

            elif len(matched_districts) == 1:
                strategy_name = StrategyName.DISTRICT_SUMMARY
                internal_reason = f"District entity '{matched_districts[0]}' detected. Generating focused district summary response."

            elif article_count > 1:
                strategy_name = StrategyName.MULTI_ARTICLE_SUMMARY
                internal_reason = f"Multiple articles ({article_count}) retrieved. Synthesizing multi-article summary response."

            else:
                strategy_name = StrategyName.TOPIC_SUMMARY
                internal_reason = "Specific topic query matched. Generating direct factual topic response."

        # -------------------------------------------------------------
        # 2. Strategy Flags & Policy Attributes Resolution
        # -------------------------------------------------------------
        requires_fallback = (strategy_name == StrategyName.NO_INFORMATION)

        requires_related_news = (
            active_policy in [ResponsePolicy.BALANCED, ResponsePolicy.HELPFUL]
            and strategy_name in [StrategyName.PARTIAL_INFORMATION, StrategyName.RELATED_INFORMATION, StrategyName.NO_INFORMATION]
        )

        requires_missing_information_notice = (
            strategy_name in [StrategyName.PARTIAL_INFORMATION, StrategyName.RELATED_INFORMATION]
            or (confidence_level in ["MEDIUM", "LOW"] and strategy_name != StrategyName.NO_INFORMATION)
        )

        requires_multi_section_output = (
            strategy_name in [StrategyName.ENTITY_COMPARISON, StrategyName.MULTI_ARTICLE_SUMMARY, StrategyName.TIMELINE_RESPONSE]
            or (active_policy == ResponsePolicy.HELPFUL and strategy_name in [StrategyName.PARTIAL_INFORMATION, StrategyName.RELATED_INFORMATION])
        )

        strategy_obj = ResponseStrategy(
            strategy_name=strategy_name.value if isinstance(strategy_name, StrategyName) else str(strategy_name),
            response_policy=active_policy,
            confidence_level=confidence_level,
            requires_related_news=requires_related_news,
            requires_missing_information_notice=requires_missing_information_notice,
            requires_fallback=requires_fallback,
            requires_multi_section_output=requires_multi_section_output,
            recommended_prompt_version=self.config.default_prompt_version,
            internal_reason=internal_reason,
        )

        logger.info(
            "Response Strategy Selected: strategy=%s, policy=%s, confidence=%s, reason='%s'",
            strategy_obj.strategy_name,
            strategy_obj.response_policy,
            strategy_obj.confidence_level,
            strategy_obj.internal_reason,
        )

        return strategy_obj

    def _extract_people_from_query_info(
        self, query_info: QueryInfo, validation_result: Optional[IntentValidationResult]
    ) -> List[str]:
        """Extract person entities from QueryInfo or IntentValidationResult."""
        people: List[str] = []
        if validation_result:
            for ent in validation_result.matched_entities:
                if ent.startswith("Person: "):
                    people.append(ent.replace("Person: ", "").strip())
        return people

    def _extract_districts_from_query_info(
        self, query_info: QueryInfo, validation_result: Optional[IntentValidationResult]
    ) -> List[str]:
        """Extract district entities from QueryInfo or IntentValidationResult."""
        districts: List[str] = []
        if query_info and query_info.district:
            districts.append(query_info.district)
        if validation_result:
            for ent in validation_result.matched_entities:
                if ent.startswith("District: "):
                    d_name = ent.replace("District: ", "").strip()
                    if d_name not in districts:
                        districts.append(d_name)
        return districts
