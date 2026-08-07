"""Sprint 3.0.2: Prompt Manager with Response Strategy Integration for Maayboli AI.

Assembles modular, versioned prompts dynamically from reusable prompt sections,
context packages, intent validation results, and ResponseStrategy objects.
"""

import logging
from typing import Any, Dict, Optional

from prompt_templates import (
    DEFAULT_PROMPT_VERSION,
    INTENT_GUIDANCE_TEMPLATES,
    OUTPUT_FORMATTING_RULES,
    POLICY_INSTRUCTIONS,
    PROMPT_TEMPLATES_V1,
    STRATEGY_INSTRUCTIONS,
    STRICT_GENERATION_RULES,
    SYSTEM_IDENTITY,
)

logger = logging.getLogger(__name__)

__all__ = ["PromptManager"]


class PromptManager:
    """Manages prompt versions and dynamically assembles strategy-guided prompts."""

    def __init__(self, default_version: str = DEFAULT_PROMPT_VERSION):
        """Initialize PromptManager with registered template versions.

        Args:
            default_version: Default prompt version string (default: "v1.0").
        """
        self.default_version = default_version
        self._registry: Dict[str, Dict[str, Any]] = {
            "v1.0": PROMPT_TEMPLATES_V1,
        }

    def register_template_version(self, version_name: str, template_dict: Dict[str, Any]) -> None:
        """Register a new or custom prompt template version for experimentation.

        Args:
            version_name: Version string identifier (e.g. "v2.0").
            template_dict: Dict containing template sections.
        """
        self._registry[version_name] = template_dict
        logger.info("Registered new prompt template version: '%s'", version_name)

    def get_template(self, version: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve template sections dictionary for a given version.

        Args:
            version: Optional prompt version string. Uses default if None.

        Returns:
            Dict[str, Any]: Template sections.
        """
        target_version = version or self.default_version
        if target_version not in self._registry:
            logger.warning(
                "Requested prompt version '%s' not registered. Falling back to default '%s'",
                target_version,
                self.default_version,
            )
            target_version = self.default_version
        return self._registry[target_version]

    def build_prompt(
        self,
        question: str,
        formatted_context: str,
        validation_result: Optional[Any] = None,
        response_strategy: Optional[Any] = None,
        version: Optional[str] = None,
    ) -> str:
        """Dynamically assemble a complete, strategy-guided prompt payload.

        Args:
            question: Cleaned user question string.
            formatted_context: Formatted context string from ContextPackage.
            validation_result: Optional IntentValidationResult object from IntentValidator.
            response_strategy: Optional ResponseStrategy object from ResponseStrategyEngine.
            version: Optional prompt version string (default: "v1.0").

        Returns:
            str: Assembled modular prompt string ready for Gemini model invocation.
        """
        template = self.get_template(version)

        # 1. System Identity
        system_id = template.get("system_identity", SYSTEM_IDENTITY)

        # 2. Strict Generation Rules
        rules = template.get("generation_rules", STRICT_GENERATION_RULES)

        # 3. Strategy & Policy Guidance
        strategy_name = getattr(response_strategy, "strategy_name", "TOPIC_SUMMARY") if response_strategy else "TOPIC_SUMMARY"
        policy_name = getattr(response_strategy, "response_policy", "BALANCED") if response_strategy else "BALANCED"
        confidence_level = getattr(response_strategy, "confidence_level", "HIGH") if response_strategy else "HIGH"

        strategy_instr = template.get("strategy_instructions", STRATEGY_INSTRUCTIONS).get(
            strategy_name, STRATEGY_INSTRUCTIONS.get("TOPIC_SUMMARY", "")
        )
        policy_instr = template.get("policy_instructions", POLICY_INSTRUCTIONS).get(
            policy_name, POLICY_INSTRUCTIONS.get("BALANCED", "")
        )

        strategy_block = (
            f"=== RESPONSE STRATEGY & POLICY EXECUTION ===\n"
            f"Selected Strategy: {strategy_name}\n"
            f"Active Policy: {policy_name}\n"
            f"Confidence Level: {confidence_level}\n"
            f"Strategy Instruction: {strategy_instr}\n"
            f"Policy Instruction: {policy_instr}\n"
        )

        # 4. Intent Quality Gate Audit Details
        validation_details_block = ""
        if validation_result:
            retrieval_status = getattr(validation_result, "retrieval_status", "EXACT_MATCH")
            val_reason = getattr(validation_result, "validation_reason", "")
            val_score = getattr(validation_result, "overall_match_score", 100.0)

            validation_details_block = (
                f"\nINTENT QUALITY GATE AUDIT:\n"
                f"- Retrieval Status: {retrieval_status}\n"
                f"- Quality Score: {val_score}%\n"
                f"- Audit Reason: {val_reason}\n"
            )

        # 5. Output Formatting Rules
        fmt_rules = template.get("formatting_rules", OUTPUT_FORMATTING_RULES)

        # 6. Assemble Sections into Final Prompt
        prompt_sections = [
            f"=== SYSTEM IDENTITY ===\n{system_id}",
            f"=== GENERATION RULES ===\n{rules}",
            f"{strategy_block}{validation_details_block}",
            f"=== RESPONSE FORMATTING RULES ===\n{fmt_rules}",
            f"=== RETRIEVED NEWS CONTEXT ===\n{formatted_context if formatted_context else '[No Relevant Articles]'}",
            f"=== USER QUESTION ===\n{question}",
        ]

        final_prompt = "\n\n".join(prompt_sections)
        logger.debug(
            "Assembled strategy-guided prompt (version=%s, strategy=%s, policy=%s, length=%d)",
            template.get("version", "v1.0"),
            strategy_name,
            policy_name,
            len(final_prompt),
        )
        return final_prompt
