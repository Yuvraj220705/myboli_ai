"""Comprehensive unit test suite for Conversational Behavior & Prompt System.

Tests prompt construction, conversational behavior rules, mixed-intent prompts,
offline fallbacks, and anti-regression behavior for news queries and unknown entity guardrails.
"""

import unittest
import sys
from pathlib import Path

# Add src to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from context_builder import ContextBuilder, ContextPackage
from generation_engine import GenerationEngine
from intent_validator import IntentValidator
from prompt_manager import PromptManager
from prompt_templates import (
    CONVERSATIONAL_BEHAVIOR,
    NO_ARTICLES_MSG,
    UNSUPPORTED_SCOPE_MSG,
    STRICT_GENERATION_RULES,
)
from query_processor import process_query


class TestConversationalBehavior(unittest.TestCase):
    """Test suite for Conversational Prompt System integration."""

    @classmethod
    def setUpClass(cls):
        cls.prompt_manager = PromptManager()
        cls.context_builder = ContextBuilder()
        cls.intent_validator = IntentValidator()
        cls.generation_engine = GenerationEngine(prompt_manager=cls.prompt_manager)

    def test_prompt_manager_includes_conversational_section(self):
        """Verify that PromptManager includes CONVERSATIONAL BEHAVIOR in assembled prompts."""
        prompt = self.prompt_manager.build_prompt(
            question="Hi",
            formatted_context="[No Relevant Articles]",
        )
        self.assertIn("=== CONVERSATIONAL BEHAVIOR ===", prompt)
        self.assertIn("Casual Conversation vs. Factual News Queries", prompt)
        self.assertIn("Do NOT claim information is unavailable", prompt)

    def test_casual_greetings_prompt_assembly(self):
        """Verify prompt payload structure for English, Marathi, and code-mixed greetings."""
        test_queries = ["Hi", "Hello", "नमस्कार", "good morning"]
        for q in test_queries:
            with self.subTest(query=q):
                prompt = self.prompt_manager.build_prompt(
                    question=q,
                    formatted_context="",
                )
                self.assertIn(f"=== USER QUESTION ===\n{q}", prompt)
                self.assertIn("CONVERSATIONAL BEHAVIOR", prompt)

    def test_identity_and_capability_prompt_assembly(self):
        """Verify prompt payload structure for identity and capability questions."""
        queries = ["Who are you?", "तू कोण आहेस?", "What can you do?", "तू काय करू शकतोस?"]
        for q in queries:
            with self.subTest(query=q):
                prompt = self.prompt_manager.build_prompt(
                    question=q,
                    formatted_context="[No Relevant Articles]",
                )
                self.assertIn("=== SYSTEM IDENTITY ===", prompt)
                self.assertIn("=== CONVERSATIONAL BEHAVIOR ===", prompt)

    def test_mixed_greeting_and_news_query_prompt(self):
        """Verify prompt assembly when input combines greeting + news query."""
        mixed_q = "हाय, आज पुण्यात काय झालं?"
        ctx_pkg = self.context_builder.build_context([
            {
                "id": 101,
                "title": "पुण्यात जोरदार पाऊस",
                "content": "पुण्यात आज हवामान विभागाने यलो अलर्ट जारी केला आहे.",
                "district_name": "पुणे",
                "category_name": "हवामान",
                "publish_date": "2026-08-08",
            }
        ])
        prompt = self.prompt_manager.build_prompt(
            question=mixed_q,
            formatted_context=ctx_pkg.formatted_context,
        )
        self.assertIn("Acknowledge the greeting briefly", prompt)
        self.assertIn("पुण्यात आज हवामान विभागाने यलो अलर्ट जारी केला आहे", prompt)

    def test_unknown_entity_guardrail_precedence(self):
        """Verify that Unknown Entity Guardrail maintains strict precedence over conversational logic."""
        unsupported_q = "जो बायडेन भारतात कधी येणार?"
        query_info = process_query(unsupported_q)
        empty_pkg = self.context_builder.build_context([])
        
        result = self.generation_engine.generate(
            question=unsupported_q,
            context_pkg=empty_pkg,
            query_info=query_info,
        )
        self.assertEqual(result["answer"], UNSUPPORTED_SCOPE_MSG)

    def test_pure_news_query_grounding_rules(self):
        """Verify that pure news queries retain strict grounding rules in assembled prompts."""
        news_q = "आज पुण्यात काय घडलं?"
        prompt = self.prompt_manager.build_prompt(
            question=news_q,
            formatted_context="[News Article Content]",
        )
        self.assertIn("STRICT GROUNDING & ANTI-HALLUCINATION RULES", prompt)
        self.assertIn("Use ONLY the facts provided", prompt)


if __name__ == "__main__":
    unittest.main()
