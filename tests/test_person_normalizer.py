"""Unit tests for Sprint 1.2.2: Person Name Normalizer module."""

import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_normalizer import (
    DEFAULT_CANONICAL_PEOPLE,
    MatchedPerson,
    PersonNormalizationResult,
    PersonNormalizer,
)


def test_person_spelling_corrections():
    normalizer = PersonNormalizer()

    # 1. Simple spelling mistake: "अमीत साह" -> "अमित शाह"
    res = normalizer.normalize_query("अमीत साह")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].canonical_name == "अमित शाह"
    assert res.matched_people[0].was_corrected is True

    # 2. Simple spelling mistake: "पावार" -> "अजित पवार"
    res = normalizer.normalize_query("अजित पावार")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].canonical_name == "अजित पवार"

    # 3. Spelling mistake: "राउत" -> "विनायक राऊत"
    res = normalizer.normalize_query("राउत बातमी")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].canonical_name == "विनायक राऊत"


def test_joined_token_splitting():
    normalizer = PersonNormalizer()

    # Joined token: "अमीतशाह" -> "अमित शाह"
    res = normalizer.normalize_query("अमीतशाह")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].canonical_name == "अमित शाह"
    assert res.matched_people[0].was_corrected is True
    assert "अमित शाह" in res.normalized_query


def test_partial_name_and_surname_resolution():
    normalizer = PersonNormalizer()

    # Unambiguous surname: "फडणविस" -> "देवेंद्र फडणवीस"
    res = normalizer.normalize_query("फडणविस")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].canonical_name == "देवेंद्र फडणवीस"
    assert res.matched_people[0].ambiguity_detected is False


def test_ambiguity_detection():
    # Inject dataset with two people sharing the same surname "पवार"
    ambiguous_dataset = [
        {"id": 1, "name": "अजित पवार"},
        {"id": 2, "name": "शरद पवार"},
    ]
    normalizer = PersonNormalizer(people_dataset=ambiguous_dataset)

    # Query with ambiguous surname "पवार" without first name
    res = normalizer.normalize_query("पवार भाषण")
    assert len(res.matched_people) == 1
    assert res.matched_people[0].ambiguity_detected is True


if __name__ == "__main__":
    print("Running Person Normalizer Unit Tests...")
    test_person_spelling_corrections()
    test_joined_token_splitting()
    test_partial_name_and_surname_resolution()
    test_ambiguity_detection()
    print("✅ All Person Normalizer Unit Tests Passed Successfully!")
