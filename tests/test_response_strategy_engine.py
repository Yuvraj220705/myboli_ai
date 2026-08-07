"""Unit tests for Sprint 3.0.2 Response Strategy Engine and integrations."""

import sys
from pathlib import Path

# Add src to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import unittest
from unittest.mock import MagicMock

from context_builder import ContextPackage
from intent_validator import IntentValidationResult
from prompt_manager import PromptManager
from query_processor import QueryInfo
from response_strategy_engine import ResponseStrategy, ResponseStrategyEngine
from strategy_config import ResponsePolicy, StrategyConfig, StrategyName
from generation_engine import GenerationEngine


class TestResponseStrategyEngine(unittest.TestCase):
    """Test suite for ResponseStrategyEngine strategy selection and policy flags."""

    def setUp(self):
        self.engine = ResponseStrategyEngine()
        self.dummy_article = MagicMock()
        self.dummy_article.id = 1
        self.dummy_article.title = "Test News Title"
        self.dummy_article.content = "Test News Content body..."
        self.dummy_article.district = "Pune"
        self.dummy_article.category = "Politics"

    def _create_mock_context_pkg(self, article_count=1):
        articles = [self.dummy_article] * article_count
        sources = [{"id": i + 1, "title": f"Title {i+1}"} for i in range(article_count)]
        return ContextPackage(
            articles=articles,
            sources=sources,
            formatted_context="Sample context content",
            article_count=article_count,
            original_article_count=article_count,
            snippet_count=article_count,
            characters_before=500,
            characters_after=400,
            estimated_tokens_before=125,
            estimated_tokens_after=100,
            compression_ratio=20.0,
            total_characters=400,
            estimated_tokens=100,
            is_truncated=False,
        )


    def test_no_information_strategy(self):
        """Test NO_MATCH or empty articles yields NO_INFORMATION strategy."""
        q_info = QueryInfo(original_query="अमेरिकेचे अध्यक्ष", clean_query="अमेरिकेचे अध्यक्ष", date=None, district=None, category=None)
        val_res = IntentValidationResult(
            overall_match_score=0.0,
            confidence="LOW",
            retrieval_status="NO_MATCH",
            validation_reason="No articles",
            district_match=False,
            person_match=False,
            category_match=False,
            date_match=False,
        )
        ctx_pkg = ContextPackage(articles=[], sources=[], formatted_context="")

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.NO_INFORMATION)
        self.assertTrue(strat.requires_fallback)
        self.assertEqual(strat.confidence_level, "LOW")

    def test_related_information_strategy(self):
        """Test RELATED_MATCH status yields RELATED_INFORMATION strategy."""
        q_info = QueryInfo(original_query="पुण्यात पाऊस", clean_query="पाऊस", date=None, district="Pune", category=None)
        val_res = IntentValidationResult(
            overall_match_score=45.0,
            confidence="LOW",
            retrieval_status="RELATED_MATCH",
            validation_reason="Missing topic: पाऊस",
            district_match=True,
            person_match=False,
            category_match=False,
            date_match=False,
            missing_topics=["पाऊस"],
        )
        ctx_pkg = self._create_mock_context_pkg(1)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.RELATED_INFORMATION)
        self.assertTrue(strat.requires_missing_information_notice)
        self.assertTrue(strat.requires_related_news)

    def test_partial_information_strategy(self):
        """Test PARTIAL_MATCH status yields PARTIAL_INFORMATION strategy."""
        q_info = QueryInfo(original_query="अमित शाह पुणे दौरा", clean_query="अमित शाह दौरा", date=None, district="Pune", category=None)
        val_res = IntentValidationResult(
            overall_match_score=65.0,
            confidence="MEDIUM",
            retrieval_status="PARTIAL_MATCH",
            validation_reason="Missing topic: दौरा",
            district_match=True,
            person_match=True,
            category_match=False,
            date_match=False,
            missing_topics=["दौरा"],
        )
        ctx_pkg = self._create_mock_context_pkg(2)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.PARTIAL_INFORMATION)
        self.assertTrue(strat.requires_missing_information_notice)

    def test_latest_news_strategy(self):
        """Test EXACT_MATCH with latest news intent yields LATEST_NEWS strategy."""
        q_info = QueryInfo(original_query="आजच्या ताज्या बातम्या", clean_query="ताज्या बातम्या", date=None, district=None, category=None, is_latest_news=True)
        val_res = IntentValidationResult(
            overall_match_score=100.0,
            confidence="HIGH",
            retrieval_status="EXACT_MATCH",
            validation_reason="Exact match",
            district_match=False,
            person_match=False,
            category_match=True,
            date_match=False,
        )
        ctx_pkg = self._create_mock_context_pkg(3)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.LATEST_NEWS)
        self.assertFalse(strat.requires_fallback)

    def test_person_summary_strategy(self):
        """Test EXACT_MATCH with single person entity yields PERSON_SUMMARY strategy."""
        q_info = QueryInfo(original_query="अमित शाह विधान", clean_query="अमित शाह विधान", date=None, district=None, category=None)
        val_res = IntentValidationResult(
            overall_match_score=100.0,
            confidence="HIGH",
            retrieval_status="EXACT_MATCH",
            validation_reason="Matched Person: अमित शाह",
            district_match=False,
            person_match=True,
            category_match=True,
            date_match=False,
            matched_entities=["Person: अमित शाह"],
        )
        ctx_pkg = self._create_mock_context_pkg(1)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.PERSON_SUMMARY)

    def test_district_summary_strategy(self):
        """Test EXACT_MATCH with district entity yields DISTRICT_SUMMARY strategy."""
        q_info = QueryInfo(original_query="सिंधुदुर्ग घडामोडी", clean_query="सिंधुदुर्ग घडामोडी", date=None, district="Sindhudurg", category=None)
        val_res = IntentValidationResult(
            overall_match_score=100.0,
            confidence="HIGH",
            retrieval_status="EXACT_MATCH",
            validation_reason="Matched District: Sindhudurg",
            district_match=True,
            person_match=False,
            category_match=True,
            date_match=False,
            matched_entities=["District: Sindhudurg"],
        )
        ctx_pkg = self._create_mock_context_pkg(1)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.DISTRICT_SUMMARY)

    def test_entity_comparison_strategy(self):
        """Test multi-entity query yields ENTITY_COMPARISON strategy."""
        q_info = QueryInfo(original_query="अमित शाह आणि देवेंद्र फडणवीस भेट", clean_query="अमित शाह फडणवीस भेट", date=None, district=None, category=None)
        val_res = IntentValidationResult(
            overall_match_score=100.0,
            confidence="HIGH",
            retrieval_status="EXACT_MATCH",
            validation_reason="Matched people",
            district_match=False,
            person_match=True,
            category_match=True,
            date_match=False,
            matched_entities=["Person: अमित शाह", "Person: देवेंद्र फडणवीस"],
        )
        ctx_pkg = self._create_mock_context_pkg(2)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.ENTITY_COMPARISON)
        self.assertTrue(strat.requires_multi_section_output)

    def test_timeline_response_strategy(self):
        """Test query with date or timeline keywords yields TIMELINE_RESPONSE strategy."""
        q_info = QueryInfo(original_query="१ ऑगस्ट २०२६ चे वेळापत्रक", clean_query="वेळापत्रक", date="2026-08-01", district=None, category=None)
        val_res = IntentValidationResult(
            overall_match_score=100.0,
            confidence="HIGH",
            retrieval_status="EXACT_MATCH",
            validation_reason="Matched Date",
            district_match=False,
            person_match=False,
            category_match=True,
            date_match=True,
        )
        ctx_pkg = self._create_mock_context_pkg(2)

        strat = self.engine.select_strategy(q_info, ctx_pkg, val_res)

        self.assertEqual(strat.strategy_name, StrategyName.TIMELINE_RESPONSE)

    def test_policy_behavior_strict_balanced_helpful(self):
        """Test STRICT, BALANCED, and HELPFUL policy flags."""
        q_info = QueryInfo(original_query="रत्नागिरी पाऊस", clean_query="पाऊस", date=None, district="Ratnagiri", category=None)
        val_res = IntentValidationResult(
            overall_match_score=45.0,
            confidence="LOW",
            retrieval_status="RELATED_MATCH",
            validation_reason="Missing topic: पाऊस",
            district_match=True,
            person_match=False,
            category_match=False,
            date_match=False,
        )
        ctx_pkg = self._create_mock_context_pkg(1)

        # STRICT Policy: never offer related news
        strat_strict = self.engine.select_strategy(q_info, ctx_pkg, val_res, policy="STRICT")
        self.assertEqual(strat_strict.response_policy, "STRICT")
        self.assertFalse(strat_strict.requires_related_news)

        # BALANCED Policy: offers related news for RELATED_MATCH
        strat_balanced = self.engine.select_strategy(q_info, ctx_pkg, val_res, policy="BALANCED")
        self.assertEqual(strat_balanced.response_policy, "BALANCED")
        self.assertTrue(strat_balanced.requires_related_news)

        # HELPFUL Policy: requires multi-section output and offers related news
        strat_helpful = self.engine.select_strategy(q_info, ctx_pkg, val_res, policy="HELPFUL")
        self.assertEqual(strat_helpful.response_policy, "HELPFUL")
        self.assertTrue(strat_helpful.requires_related_news)
        self.assertTrue(strat_helpful.requires_multi_section_output)

    def test_prompt_manager_integration(self):
        """Test PromptManager incorporates ResponseStrategy into assembled prompt."""
        pm = PromptManager()
        q = "अमित शाह सभेची बातमी"
        ctx = "अमित शाह यांनी सभेला संबोधित केले."
        strat = ResponseStrategy(
            strategy_name=StrategyName.PERSON_SUMMARY.value,
            response_policy="BALANCED",
            confidence_level="HIGH",
            requires_related_news=False,
            requires_missing_information_notice=False,
            requires_fallback=False,
            requires_multi_section_output=False,
            recommended_prompt_version="v1.0",
            internal_reason="Person summary test",
        )

        prompt = pm.build_prompt(question=q, formatted_context=ctx, response_strategy=strat)

        self.assertIn("Selected Strategy: PERSON_SUMMARY", prompt)
        self.assertIn("Active Policy: BALANCED", prompt)
        self.assertIn("Confidence Level: HIGH", prompt)
        self.assertIn(q, prompt)

    def test_generation_engine_integration_fast_path(self):
        """Test GenerationEngine uses strategy fast-path when NO_INFORMATION is selected."""
        gen_engine = GenerationEngine(api_key="fake_key")
        q_info = QueryInfo(original_query="unknown entity query", clean_query="unknown entity query", date=None, district=None, category=None)
        val_res = IntentValidationResult(
            overall_match_score=0.0,
            confidence="LOW",
            retrieval_status="NO_MATCH",
            validation_reason="No match found",
            district_match=False,
            person_match=False,
            category_match=False,
            date_match=False,
        )
        ctx_pkg = ContextPackage(articles=[], sources=[], formatted_context="")

        res = gen_engine.generate(question="unknown entity query", context_pkg=ctx_pkg, validation_result=val_res, query_info=q_info)

        self.assertIn("माझ्याकडे या प्रश्नासंबंधी कोणतीही प्रकाशित माहिती उपलब्ध नाही", res["answer"])
        self.assertIsNotNone(res["strategy"])
        self.assertEqual(res["strategy"].strategy_name, StrategyName.NO_INFORMATION)


if __name__ == "__main__":
    unittest.main()
