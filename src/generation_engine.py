"""Sprint 3.0.2: Generation Engine with Strategy Integration for Maayboli AI.

Provides a modular Answer Generation Engine that orchestrates PromptManager,
ContextPackage, IntentValidationResult, and ResponseStrategy payloads for Gemini API model invocation.
"""

import logging
import os
import time
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai

from context_builder import ContextPackage
from intent_validator import IntentValidationResult
from prompt_manager import PromptManager
from response_strategy_engine import ResponseStrategy, ResponseStrategyEngine
from strategy_config import ResponsePolicy
from prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    ERROR_MSG,
    INVALID_QUERY_MSG,
    NO_ARTICLES_MSG,
)

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

__all__ = ["GenerationEngine"]


class GenerationEngine:
    """Modular generation engine for executing strategy-guided Gemini answer generation."""

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        strategy_engine: Optional[ResponseStrategyEngine] = None,
        model_name: str = GEMINI_MODEL,
        api_key: Optional[str] = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ):
        """Initialize GenerationEngine.

        Args:
            prompt_manager: Optional PromptManager instance (creates default if None).
            strategy_engine: Optional ResponseStrategyEngine instance (creates default if None).
            model_name: Gemini model name string.
            api_key: Optional explicit Gemini API key (reads environment if None).
            prompt_version: Default prompt template version string (default: "v1.0").
        """
        self.prompt_manager = prompt_manager or PromptManager(default_version=prompt_version)
        self.strategy_engine = strategy_engine or ResponseStrategyEngine()
        self.model_name = model_name
        self.prompt_version = prompt_version

        _key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        if _key:
            try:
                self.client = genai.Client(api_key=_key)
            except Exception as e:
                logger.error("Failed to initialize Gemini Client in GenerationEngine: %s", e)
        else:
            logger.warning("GEMINI_API_KEY environment variable is not set.")

    def generate(
        self,
        question: str,
        context_pkg: ContextPackage,
        validation_result: Optional[IntentValidationResult] = None,
        response_strategy: Optional[ResponseStrategy] = None,
        policy: Optional[str] = None,
        version: Optional[str] = None,
        query_info: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Execute grounded answer generation workflow adhering to ResponseStrategy.

        Args:
            question: Cleaned user question string.
            context_pkg: ContextPackage object containing formatted context and sources.
            validation_result: Optional IntentValidationResult object from IntentValidator.
            response_strategy: Optional explicit ResponseStrategy object. Derived if None.
            policy: Optional response policy string ("STRICT", "BALANCED", "HELPFUL").
            version: Optional prompt version string (default: "v1.0").
            query_info: Optional QueryInfo object (used for strategy derivation if needed).

        Returns:
            Dict[str, Any]: Dictionary containing:
                - 'answer' (str): Generated grounded Marathi response.
                - 'sources' (List[int]): Source article database IDs.
                - 'validation' (IntentValidationResult): Quality Gate audit result.
                - 'strategy' (ResponseStrategy): Selected response strategy object.
                - 'prompt_version' (str): Prompt template version used.
        """
        active_version = version or self.prompt_version

        if not question or not question.strip():
            return {
                "answer": INVALID_QUERY_MSG,
                "sources": [],
                "validation": validation_result,
                "strategy": None,
                "prompt_version": active_version,
            }

        clean_q = question.strip()
        source_ids = [s["id"] for s in context_pkg.sources] if context_pkg and context_pkg.sources else []
        articles = context_pkg.articles if context_pkg else []

        # 1. Determine ResponseStrategy via ResponseStrategyEngine if not provided
        if response_strategy is None:
            # Reconstruct minimal QueryInfo wrapper if query_info is not provided
            if query_info is None:
                class _QueryInfoWrapper:
                    def __init__(self, q: str):
                        self.original_query = q
                        self.clean_query = q
                        self.district = None
                        self.category = None
                        self.date = None
                        self.latest_news = False
                query_info = _QueryInfoWrapper(clean_q)

            strategy = self.strategy_engine.select_strategy(
                query_info=query_info,
                context_pkg=context_pkg,
                validation_result=validation_result,
                policy=policy,
            )
        else:
            strategy = response_strategy

        # Internal Explainability Logging
        retrieval_status = getattr(validation_result, "retrieval_status", "UNKNOWN") if validation_result else "UNKNOWN"
        logger.info(
            "INTERNAL AUDIT LOG -> Response Strategy: %s, Prompt Version: %s, Intent Validation Status: %s, "
            "Confidence Level: %s, Source Articles: %d, Policy: %s",
            strategy.strategy_name,
            active_version,
            retrieval_status,
            strategy.confidence_level,
            len(articles),
            strategy.response_policy,
        )

        # 2. Fast-path check: NO_INFORMATION strategy / empty context
        if strategy.requires_fallback or not articles:
            logger.info("Fast-path fallback triggered for question '%s' (Strategy=%s)", clean_q[:50], strategy.strategy_name)
            
            # Construct polite policy-aware fallback response
            if strategy.requires_related_news and articles:
                fallback_msg = f"माझ्याकडे या विशिष्ट विषयासंबंधी प्रकाशित बातमी उपलब्ध नाही. परंतु खालील संबंधित बातम्या उपलब्ध आहेत:\n\n{articles[0].title} - {articles[0].content[:200]}..."
            else:
                fallback_msg = NO_ARTICLES_MSG

            return {
                "answer": fallback_msg,
                "sources": source_ids if strategy.requires_related_news else [],
                "validation": validation_result,
                "strategy": strategy,
                "prompt_version": active_version,
            }

        # 3. Assemble modular prompt via PromptManager using ResponseStrategy
        prompt = self.prompt_manager.build_prompt(
            question=clean_q,
            formatted_context=context_pkg.formatted_context,
            validation_result=validation_result,
            response_strategy=strategy,
            version=active_version,
        )

        # 4. Check client initialization
        if self.client is None:
            logger.error("Gemini Client is not initialized in GenerationEngine.")
            return {
                "answer": ERROR_MSG,
                "sources": source_ids,
                "validation": validation_result,
                "strategy": strategy,
                "prompt_version": active_version,
            }

        # 5. Invoke Gemini API model with retries for transient 503/429 errors
        max_retries = 2
        backoff_sec = 0.5

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )

                answer_text = response.text.strip() if response and response.text else NO_ARTICLES_MSG

                if NO_ARTICLES_MSG in answer_text and not strategy.requires_related_news:
                    return {
                        "answer": NO_ARTICLES_MSG,
                        "sources": [],
                        "validation": validation_result,
                        "strategy": strategy,
                        "prompt_version": active_version,
                    }

                logger.info("Successfully generated answer for question '%s' (strategy=%s, version=%s)", clean_q[:50], strategy.strategy_name, active_version)
                return {
                    "answer": answer_text,
                    "sources": source_ids,
                    "validation": validation_result,
                    "strategy": strategy,
                    "prompt_version": active_version,
                }

            except Exception as e:
                err_str = str(e)
                if ("503" in err_str or "429" in err_str or "UNAVAILABLE" in err_str) and attempt < max_retries:
                    logger.warning("Gemini API transient error (%s). Retrying %d/%d in %.1fs...", err_str[:80], attempt, max_retries, backoff_sec)
                    time.sleep(backoff_sec)
                    backoff_sec *= 1.5
                else:
                    logger.warning("Gemini API unavailable or rate-limited: %s. Using grounded context answer.", err_str[:80])
                    # Grounded context fallback answer
                    first_art = articles[0]
                    fallback_ans = f"प्राप्त माहितीनुसार: {first_art.title} - {first_art.content[:200]}..."
                    return {
                        "answer": fallback_ans,
                        "sources": source_ids,
                        "validation": validation_result,
                        "strategy": strategy,
                        "prompt_version": active_version,
                    }
