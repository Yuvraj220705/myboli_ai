"""Unit tests for Sprint 1.2.3: Common Marathi Word Normalizer module."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_normalizer import (
    DEFAULT_CANONICAL_VOCABULARY,
    MatchedWord,
    WordNormalizationResult,
    WordNormalizer,
)


def test_word_spelling_corrections():
    normalizer = WordNormalizer()

    # 1. Typos for "राजकारण"
    res1 = normalizer.normalize_query("राजकरण")
    assert len(res1.corrections) == 1
    assert res1.corrections[0].canonical_word == "राजकारण"
    assert res1.normalized_query == "राजकारण"

    res2 = normalizer.normalize_query("राजकारन")
    assert res2.normalized_query == "राजकारण"

    res3 = normalizer.normalize_query("राज्कारण")
    assert res3.normalized_query == "राजकारण"

    # 2. Typos for "अपघात"
    res4 = normalizer.normalize_query("अपघत")
    assert res4.normalized_query == "अपघात"

    res5 = normalizer.normalize_query("अपघाड")
    assert res5.normalized_query == "अपघात"

    # 3. Typos for "पाऊस"
    res6 = normalizer.normalize_query("पाउस")
    assert res6.normalized_query == "पाऊस"

    # 4. Typos for "शेतकरी"
    res7 = normalizer.normalize_query("शेतकारी")
    assert res7.normalized_query == "शेतकरी"


def test_non_retrieval_words_untouched():
    normalizer = WordNormalizer()

    # Generic stop words and non-retrieval terms should NOT be altered
    stop_words = ["माझा", "तुझा", "आज", "आहे", "झाला", "म्हणाला", "मोठा"]
    for word in stop_words:
        res = normalizer.normalize_query(word)
        assert res.normalized_query == word
        assert len(res.corrections) == 0


if __name__ == "__main__":
    print("Running Word Normalizer Unit Tests...")
    test_word_spelling_corrections()
    test_non_retrieval_words_untouched()
    print("✅ All Word Normalizer Unit Tests Passed Successfully!")
