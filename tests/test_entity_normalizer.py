"""Sprint 1.2.1: Unit tests for District Normalization in entity_normalizer.py."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_normalizer import (
    DistrictNormalizer,
    DistrictNormalizationResult,
    MatchedDistrict,
    normalize_unicode,
    strip_district_suffix,
    tokenize_query,
)


def test_unicode_normalization():
    """Test Stage 1: NFC Unicode normalization."""
    assert normalize_unicode("कोल्हापूर") == "कोल्हापूर"
    assert normalize_unicode("") == ""
    print("[PASS] test_unicode_normalization passed")


def test_tokenization():
    """Test Stage 2: Devanagari query tokenization."""
    tokens = tokenize_query("कोलापुर पाउस आणि पुणे बातमी")
    assert tokens == ["कोलापुर", "पाउस", "आणि", "पुणे", "बातमी"]
    print("[PASS] test_tokenization passed")


def test_district_suffix_stripping():
    """Test Stage 3: District location suffix stripping."""
    assert strip_district_suffix("कोल्हापुरात") == "कोल्हापुर"
    assert strip_district_suffix("पुण्यामध्ये") == "पुण्या"
    assert strip_district_suffix("सिंधुदुर्गात") == "सिंधुदुर्ग"
    assert strip_district_suffix("साताऱ्यात") == "साताऱ्य"
    assert strip_district_suffix("बातमी") == "बातमी"
    print("[PASS] test_district_suffix_stripping passed")


def test_district_matching():
    """Test Stage 4: RapidFuzz district matching on exact support examples."""
    normalizer = DistrictNormalizer()

    # Test cases from prompt
    test_cases = [
        ("कोलापुर", "कोल्हापूर"),
        ("कोल्हापुरात", "कोल्हापूर"),
        ("कोलहापूर", "कोल्हापूर"),
        ("नागपुर", "नागपूर"),
        ("पुण्यात", "पुणे"),
        ("सिंदुदुर्ग", "सिंधुदुर्ग"),
    ]

    for raw, expected_canonical in test_cases:
        res = normalizer.normalize_query(raw)
        assert len(res.matched_districts) == 1, f"Failed to match district for input '{raw}'"
        matched = res.matched_districts[0]
        assert matched.canonical_name == expected_canonical, (
            f"Expected '{expected_canonical}', got '{matched.canonical_name}' for input '{raw}'"
        )

    print("[PASS] test_district_matching passed")


def test_dataclass_output():
    """Test DistrictNormalizationResult and MatchedDistrict dataclasses."""
    normalizer = DistrictNormalizer()
    res = normalizer.normalize_query("कोलापुरात मुसळधार पाऊस")

    assert isinstance(res, DistrictNormalizationResult)
    assert len(res.matched_districts) == 1
    assert isinstance(res.matched_districts[0], MatchedDistrict)
    assert res.matched_districts[0].canonical_name == "कोल्हापूर"
    assert res.matched_districts[0].was_corrected is True
    assert "मुसळधार" in res.unmatched_tokens

    print("[PASS] test_dataclass_output passed")


if __name__ == "__main__":
    print("==================================================")
    print(" SPRINT 1.2.1: DISTRICT NORMALIZATION UNIT TESTS ")
    print("==================================================")
    test_unicode_normalization()
    test_tokenization()
    test_district_suffix_stripping()
    test_district_matching()
    test_dataclass_output()
    print("==================================================")
    print(" ALL TESTS PASSED SUCCESSFULLY! ")
    print("==================================================")
