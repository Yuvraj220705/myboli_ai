"""Unit tests for Sprint 2.0.2: Intelligent Context Engineering (Snippet Extraction)."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from context_builder import (
    ContextArticle,
    ContextBuilder,
    ContextPackage,
    extract_snippets,
)


def test_single_keyword_query():
    text = (
        "हा पहिला उतारा आहे ज्यामध्ये काही माहिती नाही.\n\n"
        "पुण्यात मुसळधार पाऊस झाला असून सखल भागात पाणी साचले आहे.\n\n"
        "हा तिसरा उतारा आहे ज्यामध्ये इतर विषय आहे."
    )
    snippet = extract_snippets(text, query="पाऊस")
    assert "पुण्यात मुसळधार पाऊस" in snippet


def test_multiple_keyword_query():
    text = (
        "पहिला परिच्छेद बातम्यांचा आढावा देतो.\n\n"
        "केंद्रीय गृहमंत्री अमित शाह यांनी आज पुण्यात महापालिकेच्या प्रकल्पाचे उद्घाटन केले.\n\n"
        "दुसऱ्या बातमीत क्रीडा विश्वातील घडामोडींचा समावेश आहे."
    )
    snippet = extract_snippets(text, query="अमित शाह पुणे")
    assert "अमित शाह" in snippet
    assert "पुण्यात" in snippet


def test_district_only_query():
    text = (
        "पहिला भाग सामान्य माहिती आहे.\n\n"
        "कोल्हापूर जिल्ह्यात काल रात्रीपासून जोरदार पाऊस सुरू आहे.\n\n"
        "शेवटचा भाग इतर बातम्या सांगतो."
    )
    snippet = extract_snippets(text, query="कोल्हापूर")
    assert "कोल्हापूर जिल्ह्यात" in snippet


def test_person_only_query():
    text = (
        "पहिला परिच्छेद इतर राजकारण्यांबद्दल आहे.\n\n"
        "उपमुख्यमंत्री अजित पवार यांनी आज बारामतीत पत्रकारांशी संवाद साधला.\n\n"
        "हा शेवटचा परिच्छेद आहे."
    )
    snippet = extract_snippets(text, query="अजित पवार")
    assert "अजित पवार" in snippet


def test_combined_query():
    text = (
        "प्रस्तावना परिच्छेद.\n\n"
        "मुख्यमंत्री देवेंद्र फडणवीस यांनी नागपूर शहर विकासासाठी विशेष निधी मंजूर केला.\n\n"
        "निष्कर्ष परिच्छेद."
    )
    snippet = extract_snippets(text, query="देवेंद्र फडणवीस नागपूर निधी")
    assert "देवेंद्र फडणवीस" in snippet
    assert "नागपूर" in snippet


def test_large_article_compression():
    long_paras = [
        f"परिच्छेद {i}: " + "हा बातमीचा अत्यंत विस्तृत भाग आहे. " * 15
        for i in range(1, 15)
    ]
    # Place target query word in 5th paragraph
    long_paras[4] = "विशेष राजकीय घडामोडीनुसार अमित शाह यांनी पुण्यात बैठक घेतली."

    full_text = "\n\n".join(long_paras)

    builder = ContextBuilder(enable_snippets=True)
    raw = [
        {
            "id": 500,
            "title": "विस्तृत राजकीय वृत्त",
            "content": full_text,
            "district": "Pune",
            "category": "Politics",
            "createdAt": "2026-08-05",
        }
    ]

    pkg = builder.build_context(raw, query="अमित शाह पुणे")
    assert pkg.characters_after < pkg.characters_before
    assert pkg.compression_ratio > 40.0
    assert pkg.estimated_tokens_after < pkg.estimated_tokens_before
    assert "अमित शाह" in pkg.formatted_context


def test_short_article_handling():
    short_text = "पुण्यात पावसाची जोरदार हजेरी."
    snippet = extract_snippets(short_text, query="पाऊस")
    assert snippet == short_text


def test_no_keyword_overlap_fallback():
    text = (
        "हा पहिला महत्वाचा प्रस्तावना परिच्छेद आहे.\n\n"
        "हा दुसरा मुख्य परिच्छेद आहे.\n\n"
        "हा तिसरा परिच्छेद आहे."
    )
    # Query words not in text
    snippet = extract_snippets(text, query="अनपेक्षित शब्द")
    # Should fallback deterministically to lead paragraphs (paragraph 1 & 2)
    assert "हा पहिला महत्वाचा प्रस्तावना परिच्छेद" in snippet
    assert "हा दुसरा मुख्य परिच्छेद" in snippet


def test_metadata_preservation():
    builder = ContextBuilder(enable_snippets=True)
    raw = [
        {
            "id": 999,
            "title": "महत्त्वाची बातमी",
            "content": "पहिली ओळ.\n\nमुख्य माहिती परिच्छेद.\n\nशेवटची ओळ.",
            "district": "Sindhudurg",
            "category": "Weather",
            "createdAt": "2026-08-06",
            "url": "https://example.com/news/999",
        }
    ]

    pkg = builder.build_context(raw, query="माहिती")
    assert len(pkg.sources) == 1
    assert pkg.sources[0]["id"] == 999
    assert pkg.sources[0]["district"] == "Sindhudurg"
    assert pkg.sources[0]["category"] == "Weather"
    assert "District: Sindhudurg" in pkg.formatted_context
    assert "Category: Weather" in pkg.formatted_context
    assert "Published Date: 2026-08-06" in pkg.formatted_context


def test_normalized_query_matching():
    # Text contains canonical normalized spelling 'राजकारण'
    text = (
        "हा बातमीचा पहिला परिच्छेद आहे.\n\n"
        "महाराष्ट्रातील राजकारण तापले असून विविध पक्षांच्या नेत्यांनी वक्तव्ये केली आहेत.\n\n"
        "हा तिसरा परिच्छेद आहे."
    )
    # Query contains raw typo 'राजकरण'
    builder = ContextBuilder(enable_snippets=True)
    raw = [
        {
            "id": 888,
            "title": "राजकीय घडामोडी",
            "content": text,
        }
    ]
    # Pass normalized query 'राजकारण'
    pkg = builder.build_context(raw, query="राजकारण")
    assert "महाराष्ट्रातील राजकारण" in pkg.formatted_context


if __name__ == "__main__":
    print("Running Intelligent Context Engineering Unit Tests...")
    test_single_keyword_query()
    test_multiple_keyword_query()
    test_district_only_query()
    test_person_only_query()
    test_combined_query()
    test_large_article_compression()
    test_short_article_handling()
    test_no_keyword_overlap_fallback()
    test_metadata_preservation()
    test_normalized_query_matching()
    print("✅ All Intelligent Context Engineering Unit Tests Passed Successfully!")
