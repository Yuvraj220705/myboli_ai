"""Sprint 3.0.1: Generation Engine for Maayboli AI.

Provides a modular Answer Generation Engine that orchestrates PromptManager,
ContextPackage, and IntentValidationResult payloads for Gemini API model invocation.
"""

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai

from context_builder import ContextPackage
from intent_validator import IntentValidationResult
from prompt_manager import PromptManager
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
    """Modular generation engine for assembling prompts and executing grounded Gemini answer generation."""

    def __init__(
        self,
        prompt_manager: Optional[PromptManager] = None,
        model_name: str = GEMINI_MODEL,
        api_key: Optional[str] = None,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
    ):
        """Initialize GenerationEngine.

        Args:
            prompt_manager: Optional PromptManager instance (creates default if None).
            model_name: Gemini model name string.
            api_key: Optional explicit Gemini API key (reads environment if None).
            prompt_version: Default prompt template version string (default: "v1.0").
        """
        self.prompt_manager = prompt_manager or PromptManager(default_version=prompt_version)
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
        version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute grounded answer generation workflow.

        Args:
            question: Cleaned user question string.
            context_pkg: ContextPackage object containing formatted context and sources.
            validation_result: Optional IntentValidationResult object from IntentValidator.
            version: Optional prompt version string (default: "v1.0").

        Returns:
            Dict[str, Any]: Dictionary containing:
                - 'answer' (str): Generated grounded Marathi response.
                - 'sources' (List[int]): Source article database IDs.
                - 'validation' (IntentValidationResult): Quality Gate audit result.
                - 'prompt_version' (str): Prompt template version used.
        """
        if not question or not question.strip():
            return {
                "answer": INVALID_QUERY_MSG,
                "sources": [],
                "validation": validation_result,
                "prompt_version": version or self.prompt_version,
            }

        clean_q = question.strip()
        source_ids = [s["id"] for s in context_pkg.sources] if context_pkg and context_pkg.sources else []

        # 1. Fast-path check: NO_MATCH status or empty articles
        if not context_pkg or not context_pkg.articles or (validation_result and validation_result.retrieval_status == "NO_MATCH"):
            logger.info("Fast-path fallback triggered for question '%s' (NO_MATCH / empty context)", clean_q[:50])
            return {
                "answer": NO_ARTICLES_MSG,
                "sources": [],
                "validation": validation_result,
                "prompt_version": version or self.prompt_version,
            }

        # 2. Assemble modular prompt via PromptManager
        active_version = version or self.prompt_version
        prompt = self.prompt_manager.build_prompt(
            question=clean_q,
            formatted_context=context_pkg.formatted_context,
            validation_result=validation_result,
            version=active_version,
        )

        # 3. Check client initialization
        if self.client is None:
            logger.error("Gemini Client is not initialized in GenerationEngine.")
            return {
                "answer": ERROR_MSG,
                "sources": source_ids,
                "validation": validation_result,
                "prompt_version": active_version,
            }

        # 4. Invoke Gemini API model
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
            )

            answer_text = response.text.strip() if response and response.text else NO_ARTICLES_MSG

            if NO_ARTICLES_MSG in answer_text:
                return {
                    "answer": NO_ARTICLES_MSG,
                    "sources": [],
                    "validation": validation_result,
                    "prompt_version": active_version,
                }

            logger.info("Successfully generated answer for question '%s' (version=%s)", clean_q[:50], active_version)
            return {
                "answer": answer_text,
                "sources": source_ids,
                "validation": validation_result,
                "prompt_version": active_version,
            }

        except Exception as e:
            logger.error("Gemini API generation request failed: %s", e, exc_info=True)
            return {
                "answer": ERROR_MSG,
                "sources": source_ids,
                "validation": validation_result,
                "prompt_version": active_version,
            }
