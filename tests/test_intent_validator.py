"""Unit tests for Sprint 2.1: Intent Validation Layer (Quality Gate)."""

from datetime import date
import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from context_builder import ContextArticle, ContextPackage
from intent_validator import IntentValidationResult, IntentValidator
from query_processor import QueryInfo, process_query


def test_no_match_empty_context():
    validator = IntentValidator()
    q_info = process_query("पुण्यात पाऊस")
    empty_pkg = ContextPackage(formatted_context="", articles=[])

    res = validator.validate(q_info, empty_pkg)
    assert res.overall_match_score == 0.0
    assert res.confidence == "LOW"
    assert res.retrieval_status == "NO_MATCH"
    assert "No matching published articles" in res.validation_reason


def test_exact_match_district_and_person_and_topic():
    validator = IntentValidator()
    q_info = process_query("अमित शाह यांनी पुण्यात काय सांगितले?")

    art = ContextArticle(
        id=741,
        title="गृहमंत्री अमित शाह पुणे दौरा",
        content="केंद्रीय गृहमंत्री अमित शाह यांनी पुण्यात भव्य सभेला संबोधित केले.",
        district="Pune",
        category="Politics",
        date="2026-08-01",
    )
    context_str = f"Title: {art.title}\nDistrict: {art.district}\nContent: {art.content}"
    pkg = ContextPackage(formatted_context=context_str, articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.overall_match_score >= 90.0
    assert res.confidence == "HIGH"
    assert res.retrieval_status == "EXACT_MATCH"
    assert res.district_match is True
    assert res.person_match is True


def test_partial_match_missing_topic():
    validator = IntentValidator()
    # Query asks for Vinayak Raut + Sindhudurg + Rain
    q_info = process_query("विनायक राऊत सिंधुदुर्ग पाऊस")

    # Context article has Vinayak Raut + Sindhudurg, but topic is Politics (no rain)
    art = ContextArticle(
        id=1010,
        title="विनायक राऊत प्रकरणात सिंधुदुर्गात राजकीय भूकंप",
        content="शिवसेना नेते विनायक राऊत यांच्या वक्तव्यामुळे सिंधुदुर्गात राजकीय घडामोडी तापल्या आहेत.",
        district="Sindhudurg",
        category="Politics",
        date="2026-08-05",
    )
    context_str = f"Title: {art.title}\nDistrict: {art.district}\nContent: {art.content}"
    pkg = ContextPackage(formatted_context=context_str, articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.district_match is True
    assert res.person_match is True
    assert res.retrieval_status in ["PARTIAL_MATCH", "RELATED_MATCH"]
    assert "Missing topics" in res.validation_reason or "पाऊस" in res.missing_topics or "Category" in res.missing_topics


def test_district_only_query():
    validator = IntentValidator()
    q_info = process_query("कोल्हापूर बातम्या")

    art = ContextArticle(
        id=555,
        title="कोल्हापूर जिल्ह्यातील ताजी परिस्थिती",
        content="कोल्हापूर शहरात विविध उपक्रम पार पडले.",
        district="Kolhapur",
    )
    pkg = ContextPackage(formatted_context=f"District: Kolhapur\n{art.content}", articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.district_match is True
    assert res.overall_match_score == 100.0
    assert res.retrieval_status == "EXACT_MATCH"


def test_person_only_query():
    validator = IntentValidator()
    q_info = process_query("अजित पवार")

    art = ContextArticle(
        id=666,
        title="अजित पवार पत्रकार परिषद",
        content="उपमुख्यमंत्री अजित पवार यांनी माध्यमांशी बातचीत केली.",
    )
    pkg = ContextPackage(formatted_context=art.content, articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.person_match is True
    assert res.overall_match_score == 100.0
    assert res.retrieval_status == "EXACT_MATCH"


def test_date_matching():
    validator = IntentValidator()
    q_info = process_query("2026-08-01 बातम्या")

    art = ContextArticle(
        id=777,
        title="दैनिक वृत्त",
        content="दिवसभरातील महत्त्वाचे वृत्त.",
        date="2026-08-01",
    )
    pkg = ContextPackage(formatted_context=f"Published Date: 2026-08-01\n{art.content}", articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.date_match is True
    assert res.retrieval_status == "EXACT_MATCH"


def test_conflicting_entities():
    validator = IntentValidator()
    # Query asks for Nagpur news
    q_info = process_query("नागपूर बातम्या")

    # Context article is about Mumbai
    art = ContextArticle(
        id=333,
        title="मुंबई महापालिका निर्णय",
        content="मुंबई शहरात नवीन रस्ते विकास प्रकल्प जाहीर.",
        district="Mumbai",
    )
    pkg = ContextPackage(formatted_context=f"District: Mumbai\n{art.content}", articles=[art])

    res = validator.validate(q_info, pkg)
    assert res.district_match is False
    assert res.retrieval_status == "NO_MATCH"
    assert res.overall_match_score < 30.0


if __name__ == "__main__":
    print("Running Intent Validation Layer Unit Tests...")
    test_no_match_empty_context()
    test_exact_match_district_and_person_and_topic()
    test_partial_match_missing_topic()
    test_district_only_query()
    test_person_only_query()
    test_date_matching()
    test_conflicting_entities()
    print("✅ All Intent Validation Layer Unit Tests Passed Successfully!")
