"""Unit tests and evaluation runner for entity_normalizer.py."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_normalizer import (
    EntityNormalizer,
    EntityRegistry,
    EntityType,
    ExactMatchingStrategy,
    RapidFuzzMatchingStrategy,
    create_default_registry,
    normalize_unicode,
    strip_devanagari_suffix,
    tokenize_query,
)


def test_unicode_normalization():
    """Test NFC Unicode normalization."""
    raw = "कोल्हापूर"
    normalized = normalize_unicode(raw)
    assert normalized == raw
    assert normalize_unicode("") == ""
    print("[PASS] test_unicode_normalization passed")


def test_devanagari_suffix_stripping():
    """Test Marathi location and grammatical suffix stripping."""
    assert strip_devanagari_suffix("कोल्हापुरात") == "कोल्हापुर"
    assert strip_devanagari_suffix("पुण्यामध्ये") == "पुण्या"
    assert strip_devanagari_suffix("सिंधुदुर्गात") == "सिंधुदुर्ग"
    assert strip_devanagari_suffix("राजकरणाच्या") == "राजकरणा"
    assert strip_devanagari_suffix("बातमी") == "बातमी"  # no suffix
    print("[PASS] test_devanagari_suffix_stripping passed")


def test_tokenization():
    """Test tokenization of Devanagari sentences."""
    query = "अमित शाह यांच्या, सिंधुदुर्ग दौऱ्याबद्दल काय बातमी आहे?"
    tokens = tokenize_query(query)
    assert "अमित" in tokens
    assert "शाह" in tokens
    assert "सिंधुदुर्ग" in tokens
    print("[PASS] test_tokenization passed")


def test_rapidfuzz_matching():
    """Test fuzzy matching typos using RapidFuzz strategy."""
    strategy = RapidFuzzMatchingStrategy(score_cutoff=70.0)
    candidates = {
        "कोल्हापूर": "Kolhapur",
        "सिंधुदुर्ग": "Sindhudurg",
    }
    res = strategy.match("कोलापुर", candidates, min_threshold=70.0)
    assert res is not None
    canonical, score = res
    assert canonical == "Kolhapur"
    assert score >= 70.0
    print("[PASS] test_rapidfuzz_matching passed")


def test_type_isolated_matching():
    """Test that entities match strictly within their configured EntityType."""
    normalizer = EntityNormalizer()
    res = normalizer.normalize_query("अमीत शाह कोलापुर राजकरण")

    matched_types = [m.entity_type for m in res.matched_entities]
    matched_canonicals = [m.canonical_value for m in res.matched_entities]

    assert EntityType.PERSON in matched_types
    assert EntityType.DISTRICT in matched_types
    assert EntityType.CATEGORY in matched_types

    assert "Amit Shah" in matched_canonicals
    assert "Kolhapur" in matched_canonicals
    assert "Politics" in matched_canonicals

    print("[PASS] test_type_isolated_matching passed")


def test_custom_entity_injection():
    """Test injectability of custom entity types (e.g. Political Parties)."""
    registry = create_default_registry()
    parties = {
        "BJP": ["भाजपा", "भारतीय जनता पार्टी"],
        "ShivSena": ["शिवसेना", "शिंदे गट"],
    }
    registry.register_bulk(EntityType.POLITICAL_PARTY, parties)

    normalizer = EntityNormalizer(registry=registry)
    res = normalizer.normalize_query("भाजपा अध्यक्ष कोण आहेत?")

    party_matches = [m for m in res.matched_entities if m.entity_type == EntityType.POLITICAL_PARTY]
    assert len(party_matches) == 1
    assert party_matches[0].canonical_value == "BJP"

    print("[PASS] test_custom_entity_injection passed")


if __name__ == "__main__":
    print("==================================================")
    print(" RUNNING ENTITY NORMALIZER UNIT TESTS")
    print("==================================================")
    test_unicode_normalization()
    test_devanagari_suffix_stripping()
    test_tokenization()
    test_rapidfuzz_matching()
    test_type_isolated_matching()
    test_custom_entity_injection()
    print("==================================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")
