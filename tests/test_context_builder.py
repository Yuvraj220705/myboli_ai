"""Unit tests for Sprint 2.0.1: Context Builder Layer."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from context_builder import ContextArticle, ContextBuilder, ContextPackage


def test_empty_input():
    builder = ContextBuilder()
    pkg = builder.build_context([])
    assert pkg.article_count == 0
    assert pkg.formatted_context == ""
    assert pkg.estimated_tokens == 0
    assert pkg.is_truncated is False

    pkg_none = builder.build_context(None)
    assert pkg_none.article_count == 0


def test_single_article():
    builder = ContextBuilder()
    raw = [
        {
            "id": 101,
            "title": "पुण्यात मुसळधार पाऊस",
            "content": "पुणे शहरात आज सकाळी मुसळधार पाऊस झाला.",
            "district": "Pune",
            "category": "Weather",
            "createdAt": "2026-08-01",
            "url": "https://example.com/news/101",
        }
    ]

    pkg = builder.build_context(raw)
    assert pkg.article_count == 1
    assert len(pkg.articles) == 1
    assert pkg.articles[0].id == 101
    assert pkg.articles[0].district == "Pune"
    assert "Title: पुण्यात मुसळधार पाऊस" in pkg.formatted_context
    assert "District: Pune" in pkg.formatted_context
    assert "Category: Weather" in pkg.formatted_context
    assert pkg.is_truncated is False


def test_multiple_articles_and_ordering():
    builder = ContextBuilder(max_articles=5)
    raw = [
        {"id": 1, "title": "Article One", "content": "Content One"},
        {"id": 2, "title": "Article Two", "content": "Content Two"},
        {"id": 3, "title": "Article Three", "content": "Content Three"},
    ]

    pkg = builder.build_context(raw)
    assert pkg.article_count == 3
    assert pkg.articles[0].id == 1
    assert pkg.articles[1].id == 2
    assert pkg.articles[2].id == 3
    assert "--- Article 1 (ID: 1) ---" in pkg.formatted_context
    assert "--- Article 3 (ID: 3) ---" in pkg.formatted_context


def test_duplicate_id_deduplication():
    builder = ContextBuilder()
    raw = [
        {"id": 10, "title": "First Entry", "content": "Original Content"},
        {"id": 10, "title": "Duplicate Entry", "content": "Duplicate Content"},
        {"id": 20, "title": "Second Entry", "content": "Unique Content"},
    ]

    pkg = builder.build_context(raw)
    assert pkg.article_count == 2
    assert [a.id for a in pkg.articles] == [10, 20]
    assert pkg.articles[0].title == "First Entry"


def test_character_limit_truncation():
    # Set a tiny character limit (e.g. 250 chars) to force truncation
    builder = ContextBuilder(max_characters=250)
    raw = [
        {"id": 1, "title": "Short Title", "content": "A" * 100},
        {"id": 2, "title": "Long Title", "content": "B" * 500},
    ]

    pkg = builder.build_context(raw)
    assert pkg.is_truncated is True
    assert pkg.total_characters <= 250


def test_metadata_preservation():
    builder = ContextBuilder()
    raw = [
        {
            "id": 50,
            "title": "राजकीय घडामोडी",
            "content": "मंत्रिमंडळ विस्तार लवकरच होणार.",
            "district": "Mumbai",
            "category": "Politics",
            "createdAt": "2026-08-05",
            "url": "https://news.com/50",
        }
    ]

    pkg = builder.build_context(raw)
    assert len(pkg.sources) == 1
    assert pkg.sources[0]["id"] == 50
    assert pkg.sources[0]["district"] == "Mumbai"
    assert pkg.sources[0]["category"] == "Politics"
    assert pkg.sources[0]["url"] == "https://news.com/50"


if __name__ == "__main__":
    print("Running Context Builder Unit Tests...")
    test_empty_input()
    test_single_article()
    test_multiple_articles_and_ordering()
    test_duplicate_id_deduplication()
    test_character_limit_truncation()
    test_metadata_preservation()
    print("✅ All Context Builder Unit Tests Passed Successfully!")
