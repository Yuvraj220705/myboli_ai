"""Unit tests for Sprint 3.0.1: Generation Engine & Prompt Manager."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from context_builder import ContextArticle, ContextPackage
from generation_engine import GenerationEngine
from intent_validator import IntentValidationResult
from prompt_manager import PromptManager
from prompt_templates import NO_ARTICLES_MSG, PROMPT_TEMPLATES_V1


def test_prompt_manager_default_assembly():
    pm = PromptManager()
    prompt = pm.build_prompt(
        question="पुण्यात आज काय घडले?",
        formatted_context="--- Article 1 ---\nTitle: पुणे पाऊस\nContent: मुसळधार पाऊस झाला.",
    )

    assert "=== SYSTEM IDENTITY ===" in prompt
    assert "=== GENERATION RULES ===" in prompt
    assert "=== INTENT VALIDATION GUIDANCE ===" in prompt
    assert "=== RESPONSE FORMATTING RULES ===" in prompt
    assert "=== RETRIEVED NEWS CONTEXT ===" in prompt
    assert "=== USER QUESTION ===" in prompt
    assert "पुण्यात आज काय घडले?" in prompt


def test_prompt_manager_validation_status_guidance():
    pm = PromptManager()

    # Exact Match
    val_exact = IntentValidationResult(
        overall_match_score=100.0,
        confidence="HIGH",
        retrieval_status="EXACT_MATCH",
        validation_reason="All entities matched.",
        district_match=True,
        person_match=False,
        category_match=True,
        date_match=False,
    )
    p_exact = pm.build_prompt("पुणे पाऊस", "context", validation_result=val_exact)
    assert "EXACT MATCH" in p_exact

    # Partial Match
    val_partial = IntentValidationResult(
        overall_match_score=75.0,
        confidence="MEDIUM",
        retrieval_status="PARTIAL_MATCH",
        validation_reason="Person matched, topic missing.",
        district_match=True,
        person_match=True,
        category_match=False,
        date_match=False,
    )
    p_partial = pm.build_prompt("विनायक राऊत पाऊस", "context", validation_result=val_partial)
    assert "PARTIAL MATCH" in p_partial

    # Related Match
    val_related = IntentValidationResult(
        overall_match_score=45.0,
        confidence="MEDIUM",
        retrieval_status="RELATED_MATCH",
        validation_reason="Only general category matched.",
        district_match=True,
        person_match=False,
        category_match=False,
        date_match=False,
    )
    p_related = pm.build_prompt("नाशिक क्रीडा", "context", validation_result=val_related)
    assert "RELATED MATCH" in p_related

    # No Match
    val_no = IntentValidationResult(
        overall_match_score=0.0,
        confidence="LOW",
        retrieval_status="NO_MATCH",
        validation_reason="No match.",
        district_match=False,
        person_match=False,
        category_match=False,
        date_match=False,
    )
    p_no = pm.build_prompt("अज्ञात बातमी", "context", validation_result=val_no)
    assert "NO MATCH" in p_no


def test_prompt_manager_version_switching():
    pm = PromptManager()
    custom_template = {
        "version": "v2.0-experimental",
        "system_identity": "Custom System Identity v2",
        "generation_rules": "Custom Rules",
        "intent_guidance": {"EXACT_MATCH": "Custom Guidance"},
        "formatting_rules": "Custom Formatting",
    }
    pm.register_template_version("v2.0", custom_template)

    prompt_v2 = pm.build_prompt("प्रश्न", "संदर्भ", version="v2.0")
    assert "Custom System Identity v2" in prompt_v2

    # Fallback when version does not exist
    prompt_fallback = pm.build_prompt("प्रश्न", "संदर्भ", version="v99.0")
    assert "You are Maayboli AI" in prompt_fallback


def test_generation_engine_no_match_fast_path():
    engine = GenerationEngine(api_key=None)  # No API key needed for fast-path

    val_no = IntentValidationResult(
        overall_match_score=0.0,
        confidence="LOW",
        retrieval_status="NO_MATCH",
        validation_reason="No match",
        district_match=False,
        person_match=False,
        category_match=False,
        date_match=False,
    )
    empty_pkg = ContextPackage(formatted_context="", articles=[])

    res = engine.generate("भलतीच बातमी", context_pkg=empty_pkg, validation_result=val_no)
    assert res["answer"] == NO_ARTICLES_MSG
    assert res["sources"] == []
    assert res["prompt_version"] == "v1.0"


def test_generation_engine_context_and_source_retention():
    engine = GenerationEngine(api_key=None)

    art = ContextArticle(id=999, title="पुणे बातमी", content="पाऊस झाला.", district="Pune")
    pkg = ContextPackage(formatted_context="Article content", articles=[art], sources=[{"id": 999, "title": "पुणे बातमी"}])

    val_exact = IntentValidationResult(
        overall_match_score=100.0,
        confidence="HIGH",
        retrieval_status="EXACT_MATCH",
        validation_reason="Matched",
        district_match=True,
        person_match=False,
        category_match=True,
        date_match=False,
    )

    # When client is None, error message is returned with retained sources
    res = engine.generate("पुण्यात पाऊस", context_pkg=pkg, validation_result=val_exact)
    assert "sources" in res
    assert res["sources"] == [999]


if __name__ == "__main__":
    print("Running Generation Engine Unit Tests...")
    test_prompt_manager_default_assembly()
    test_prompt_manager_validation_status_guidance()
    test_prompt_manager_version_switching()
    test_generation_engine_no_match_fast_path()
    test_generation_engine_context_and_source_retention()
    print("✅ All Generation Engine Unit Tests Passed Successfully!")
