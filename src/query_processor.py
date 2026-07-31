"""Query processing and intent analysis module for Myboli AI."""

import logging
import re
from dataclasses import dataclass
from datetime import date
from typing import Dict, Optional

from date_parser import extract_date, strip_date_from_query

logger = logging.getLogger(__name__)

__all__ = [
    "QueryInfo",
    "process_query",
]


# ----------------------------
# Constants
# ----------------------------

# Maps Marathi district name (used in queries) -> English name as stored in the database
DISTRICTS: Dict[str, str] = {
    "सिंधुदुर्ग": "Sindhudurg",
    "कोल्हापूर": "Kolhapur",
    "रत्नागिरी": "Ratnagiri",
    "मुंबई": "Mumbai",
    "पुणे": "Pune",
    "सांगली": "Sangli",
    "सातारा": "Satara",
    "नाशिक": "Nashik",
}

CATEGORY_ALIASES = {
    "Politics": ["राजकारण", "राजकीय"],
    "Sports": ["क्रीडा", "खेळ"],
    "Entertainment": ["मनोरंजन", "चित्रपट"],
    "Crime": ["गुन्हे", "क्राइम"],
    "Education": ["शिक्षण"],
    "Health": ["आरोग्य"],
}

# Common Marathi suffix regex for location names (e.g. सिंधुदुर्गमध्ये, सिंधुदुर्गात, सिंधुदुर्गातील, सिंधुदुर्गचा)
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
    """
    original_query: str
    clean_query: str
    date: Optional[date]
    district: Optional[str]
    category: Optional[str]
    is_latest_news: bool = False


# ----------------------------
# Private Helpers
# ----------------------------

def _detect_district(text: str) -> Optional[str]:
    """Detect if any known district name is mentioned in the query.

    Handles Marathi location suffixes (e.g. सिंधुदुर्गमध्ये -> सिंधुदुर्ग).
    Returns the English district name as stored in the database.

    Args:
        text: The input text query.

    Returns:
        The English district name matching the database value, or None if no district is found.
    """
    for marathi_name, english_name in DISTRICTS.items():
        pattern = rf"{re.escape(marathi_name)}{_DISTRICT_SUFFIXES}"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return english_name
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
) -> str:
    """Construct a clean query string by removing dates, districts, and category words.

    Args:
        question: The raw user question string.
        detected_district: The English DB district name detected, if any.
        detected_category: The English DB canonical category name detected, if any.

    Returns:
        A cleaned, trimmed Marathi query string suitable for FULLTEXT retrieval.
        Category aliases are removed from the text but the original Marathi term is
        preserved as the fallback when no other content remains — ensuring FULLTEXT
        searches Marathi article content while SQL uses the English category filter.
    """
    # Remove date & date-filler words using date_parser
    cleaned = strip_date_from_query(question)

    # Remove the Marathi district name from the query text (reverse lookup from DISTRICTS dict)
    if detected_district:
        marathi_name = next(
            (k for k, v in DISTRICTS.items() if v == detected_district), None
        )
        if marathi_name:
            pattern = rf"{re.escape(marathi_name)}{_DISTRICT_SUFFIXES}"
            cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Remove category aliases from the query text.
    # Track the first matched Marathi alias so it can be used as FULLTEXT fallback
    # instead of the English DB key — Marathi content in articles matches better.
    matched_marathi_alias: Optional[str] = None
    if detected_category:
        aliases = CATEGORY_ALIASES.get(detected_category, [])
        for alias in aliases:
            if matched_marathi_alias is None and alias in cleaned:
                matched_marathi_alias = alias
            # Token-based removal: split query into tokens, discard matched alias tokens.
            # This avoids partial Devanagari character stripping from adjacent words.
            tokens = cleaned.split()
            alias_tokens = alias.split()
            filtered: list = []
            i = 0
            while i < len(tokens):
                # Check if alias_tokens match starting at position i
                if tokens[i:i + len(alias_tokens)] == alias_tokens:
                    i += len(alias_tokens)  # skip matched alias tokens
                else:
                    filtered.append(tokens[i])
                    i += 1
            cleaned = " ".join(filtered)

        # If stripping emptied the query, fall back to the matched Marathi alias
        # so FULLTEXT uses "राजकारण" not "Politics" against Marathi article content.
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

    # Extract date using date_parser
    detected_date = extract_date(raw_query)

    # Detect district and category
    detected_district = _detect_district(raw_query)
    detected_category = _detect_category(raw_query)

    # Generate cleaned query string
    cleaned = _clean_query(raw_query, detected_district, detected_category)

    # Detect if query requests latest news summary
    is_latest_news = any(pattern in raw_query for pattern in LATEST_NEWS_PATTERNS)

    logger.info(
        "Processed query: date=%s, district=%s, category=%s, latest_news=%s, clean_query='%s'",
        detected_date,
        detected_district,
        detected_category,
        is_latest_news,
        cleaned[:50],
    )

    return QueryInfo(
        original_query=raw_query,
        clean_query=cleaned,
        date=detected_date,
        district=detected_district,
        category=detected_category,
        is_latest_news=is_latest_news,
    )
