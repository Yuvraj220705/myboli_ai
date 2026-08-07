"""Query processing and intent analysis module for Myboli AI."""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional, Tuple

from entity_normalizer import (
    DistrictNormalizer,
    MatchedDistrict,
    MatchedPerson,
    PersonNormalizer,
    WordNormalizer,
)
from date_parser import extract_date, strip_date_from_query
from unknown_entity_guard import UnknownEntityGuard, UnknownEntityResult

logger = logging.getLogger(__name__)

__all__ = [
    "QueryInfo",
    "process_query",
    "UnknownEntityResult",
]


# ----------------------------
# Constants
# ----------------------------

# Instantiate DistrictNormalizer, PersonNormalizer & WordNormalizer instances
_DISTRICT_NORMALIZER = DistrictNormalizer()
_PERSON_NORMALIZER = PersonNormalizer()
_WORD_NORMALIZER = WordNormalizer()
_UNKNOWN_ENTITY_GUARD = UnknownEntityGuard(_DISTRICT_NORMALIZER, _PERSON_NORMALIZER, _WORD_NORMALIZER)

# Maps Canonical Marathi district name -> English name as stored in database
DISTRICTS: Dict[str, str] = {
    "सिंधुदुर्ग": "Sindhudurg",
    "कोल्हापूर": "Kolhapur",
    "रत्नागिरी": "Ratnagiri",
    "मुंबई": "Mumbai",
    "पुणे": "Pune",
    "सांगली": "Sangli",
    "सातारा": "Satara",
    "नाशिक": "Nashik",
    "नागपूर": "Nagpur",
    "अहमदनगर": "Ahmednagar",
    "छत्रपती संभाजीनगर": "Aurangabad",
    "सोलापूर": "Solapur",
    "ठाणे": "Thane",
    "पालघर": "Palghar",
    "रायगड": "Raigad",
    "जळगाव": "Jalgaon",
    "धुळे": "Dhule",
    "नंदुरबार": "Nandurbar",
    "जालना": "Jalna",
    "बीड": "Beed",
    "लातूर": "Latur",
    "धाराशिव": "Dharashiv",
    "नांदेड": "Nanded",
    "परभणी": "Parbhani",
    "हिंगोली": "Hingoli",
    "अमरावती": "Amravati",
    "अकोला": "Akola",
    "वाशीम": "Washim",
    "बुलढाणा": "Buldhana",
    "यवतमाळ": "Yavatmal",
    "वर्धा": "Wardha",
    "भंडारा": "Bhandara",
    "गोंदिया": "Gondia",
    "चंद्रपूर": "Chandrapur",
    "गडचिरोली": "Gadchiroli",
}

CATEGORY_ALIASES = {
    "Politics": ["राजकारण", "राजकीय"],
    "Sports": ["क्रीडा", "खेळ"],
    "Entertainment": ["मनोरंजन", "चित्रपट"],
    "Crime": ["गुन्हे", "क्राइम"],
    "Education": ["शिक्षण"],
    "Health": ["आरोग्य"],
}

# Common Marathi suffix regex for location names
_DISTRICT_SUFFIXES = r"(?:मध्ये|मध्येच|ात|तील|चा|ची|च्या|ने|साठी)?"


# Patterns for queries requesting general latest news (e.g., "आज काय घडलं", "ताज्या बातम्या")
LATEST_NEWS_PATTERNS = [
    "आज काय घडलं",
    "आजच्या बातम्या",
    "ताज्या बातम्या",
    "मुख्य बातमी",
    "नवीन बातम्या",
]


# ----------------------------
# Dataclasses
# ----------------------------

@dataclass
class QueryInfo:
    """Structured query information extracted from user input.

    Attributes:
        original_query: The raw input question string from the user.
        clean_query: Refined query string with date, district, and fillers stripped.
        date: Extracted target date if present, None otherwise.
        district: Extracted target district name if present, None otherwise.
        category: Extracted canonical category name if present, None otherwise.
        is_latest_news: Flag indicating if the query is a request for latest news.
        unknown_entity_result: Output from UnknownEntityGuard inspection if evaluated.
    """
    original_query: str
    clean_query: str
    date: Optional[date]
    district: Optional[str]
    category: Optional[str]
    is_latest_news: bool = False
    unknown_entity_result: Optional[UnknownEntityResult] = None


# ----------------------------
# Private Helpers
# ----------------------------

def _detect_district(text: str) -> Optional[Tuple[str, Optional[MatchedDistrict]]]:
    """Detect if any district name is mentioned in the query using DistrictNormalizer.

    Handles misspelled Devanagari names and grammatical location suffixes.

    Args:
        text: The input text query.

    Returns:
        Tuple of (English DB District Name, MatchedDistrict object) if detected, else None.
    """
    if not text:
        return None

    # Step 1: Use DistrictNormalizer to identify district entities
    result = _DISTRICT_NORMALIZER.normalize_query(text)
    if result.matched_districts:
        matched = result.matched_districts[0]
        english_name = DISTRICTS.get(matched.canonical_name)
        if english_name:
            return english_name, matched

    # Step 2: Fallback to exact regex matching if normalizer yields no match
    for marathi_name, english_name in DISTRICTS.items():
        pattern = rf"{re.escape(marathi_name)}{_DISTRICT_SUFFIXES}"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return english_name, None

    return None


def _detect_person(text: str) -> Optional[Tuple[str, Optional[MatchedPerson]]]:
    """Detect if any person name is mentioned in the query using PersonNormalizer.

    Handles spelling mistakes, joined tokens, surname expansion, and ambiguity detection.

    Args:
        text: The input text query.

    Returns:
        Tuple of (Canonical Marathi Person Name, MatchedPerson object) if detected, else None.
    """
    if not text:
        return None

    result = _PERSON_NORMALIZER.normalize_query(text)
    if result.matched_people:
        matched = result.matched_people[0]
        if not matched.ambiguity_detected:
            return matched.canonical_name, matched

    return None


def _detect_category(text: str) -> Optional[str]:
    """Detect if any category or category alias is mentioned in the query.

    Args:
        text: The input text query.

    Returns:
        The canonical category name if matched, or None if no category is found.
    """
    for canonical_name, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            pattern = rf"{re.escape(alias)}"
            if re.search(pattern, text, flags=re.IGNORECASE):
                return canonical_name
    return None


def _clean_query(
    question: str,
    detected_district: Optional[str],
    detected_category: Optional[str],
    matched_district_obj: Optional[MatchedDistrict] = None,
    matched_person_obj: Optional[MatchedPerson] = None,
) -> str:
    """Construct a clean query string by removing dates, districts, category words, and resolving person typos.

    Args:
        question: The raw user question string.
        detected_district: The English DB district name detected, if any.
        detected_category: The English DB canonical category name detected, if any.
        matched_district_obj: Optional MatchedDistrict object from DistrictNormalizer.
        matched_person_obj: Optional MatchedPerson object from PersonNormalizer.

    Returns:
        A cleaned, trimmed Marathi query string suitable for FULLTEXT retrieval.
    """
    # Remove date & date-filler words using date_parser
    cleaned = strip_date_from_query(question)

    # Correct person entity typos / joined tokens in query text
    if matched_person_obj:
        if matched_person_obj.original_text and matched_person_obj.original_text in cleaned:
            cleaned = cleaned.replace(matched_person_obj.original_text, matched_person_obj.canonical_name)

    # Remove the Marathi district name / typo tokens from the query text
    if detected_district:
        # Strip matched typo token if detected by DistrictNormalizer
        if matched_district_obj and matched_district_obj.original_token:
            pattern = rf"{re.escape(matched_district_obj.original_token)}{_DISTRICT_SUFFIXES}"
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            pattern_canonical = rf"{re.escape(matched_district_obj.canonical_name)}{_DISTRICT_SUFFIXES}"
            cleaned = re.sub(pattern_canonical, "", cleaned, flags=re.IGNORECASE)

        marathi_name = next(
            (k for k, v in DISTRICTS.items() if v == detected_district), None
        )
        if marathi_name:
            pattern = rf"{re.escape(marathi_name)}{_DISTRICT_SUFFIXES}"
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove category aliases from the query text.
    matched_marathi_alias: Optional[str] = None
    if detected_category:
        aliases = CATEGORY_ALIASES.get(detected_category, [])
        for alias in aliases:
            if matched_marathi_alias is None and alias in cleaned:
                matched_marathi_alias = alias
            tokens = cleaned.split()
            alias_tokens = alias.split()
            filtered: list = []
            i = 0
            while i < len(tokens):
                if tokens[i:i + len(alias_tokens)] == alias_tokens:
                    i += len(alias_tokens)
                else:
                    filtered.append(tokens[i])
                    i += 1
            cleaned = " ".join(filtered)

        cleaned = cleaned.strip()
        if not cleaned:
            return matched_marathi_alias or question.strip()

    # Clean up leftover whitespace and punctuation
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if cleaned else (matched_marathi_alias or question.strip())


# ----------------------------
# Public API
# ----------------------------

def process_query(question: str) -> QueryInfo:
    """Analyze and extract structured metadata from a user's question query.

    Args:
        question: The raw question string from the user.

    Returns:
        A QueryInfo dataclass instance with extracted date, district, category,
        and clean query string.
    """
    if not question:
        return QueryInfo(
            original_query="",
            clean_query="",
            date=None,
            district=None,
            category=None,
        )

    raw_query = question.strip()

    # 1. Extract date using date_parser
    detected_date = extract_date(raw_query)

    # 2. Detect district (District Normalization)
    district_res = _detect_district(raw_query)
    detected_district: Optional[str] = None
    matched_district_obj: Optional[MatchedDistrict] = None

    if district_res:
        detected_district, matched_district_obj = district_res

    # 3. Detect person (Person Normalization)
    person_res = _detect_person(raw_query)
    matched_person_obj: Optional[MatchedPerson] = None
    if person_res:
        _, matched_person_obj = person_res

    # 4. Word Normalization (Retrieval-Critical Common Marathi Vocabulary)
    word_norm_res = _WORD_NORMALIZER.normalize_query(raw_query)
    query_for_cleaning = word_norm_res.normalized_query if word_norm_res.corrections else raw_query

    # 5. Detect category
    detected_category = _detect_category(query_for_cleaning)

    # 6. Generate cleaned query string
    cleaned = _clean_query(
        query_for_cleaning,
        detected_district,
        detected_category,
        matched_district_obj,
        matched_person_obj,
    )

    # Detect if query requests latest news summary
    is_latest_news = any(pattern in raw_query for pattern in LATEST_NEWS_PATTERNS)

    # Step 7: Unknown Entity Guard inspection
    unknown_guard_res = _UNKNOWN_ENTITY_GUARD.inspect_query(raw_query)

    logger.info(
        "Processed query: date=%s, district=%s, category=%s, latest_news=%s, blocked=%s, clean_query='%s'",
        detected_date,
        detected_district,
        detected_category,
        is_latest_news,
        unknown_guard_res.should_block,
        cleaned[:50],
    )

    return QueryInfo(
        original_query=raw_query,
        clean_query=cleaned,
        date=detected_date,
        district=detected_district,
        category=detected_category,
        is_latest_news=is_latest_news,
        unknown_entity_result=unknown_guard_res,
    )
