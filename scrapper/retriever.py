"""Retrieves articles from MySQL using FULLTEXT search with date-aware retrieval."""

import logging
import re
from datetime import date, datetime
from typing import Optional

import pymysql

from db import get_connection

logger = logging.getLogger(__name__)

BODY_LIMIT = 1500

# --- Marathi digit conversion ---

_MARATHI_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _normalize_marathi_digits(text: str) -> str:
    """Convert Marathi (Devanagari) digits to ASCII digits."""
    return text.translate(_MARATHI_DIGITS)


# --- Month mappings ---

_ENGLISH_MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_MARATHI_MONTHS = {
    "जानेवारी": 1,
    "फेब्रुवारी": 2,
    "मार्च": 3,
    "एप्रिल": 4,
    "मे": 5,
    "जून": 6,
    "जुलै": 7,
    "ऑगस्ट": 8,
    "सप्टेंबर": 9,
    "ऑक्टोबर": 10,
    "नोव्हेंबर": 11,
    "डिसेंबर": 12,
}

# Combined for regex alternation
_ALL_MONTH_NAMES = "|".join(
    list(_ENGLISH_MONTHS.keys()) + list(_MARATHI_MONTHS.keys())
)

# --- Date extraction patterns ---

# Numeric: DD/MM/YYYY, DD-MM-YYYY
_PAT_NUMERIC_DMY = re.compile(
    r"(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})"
)

# Numeric: YYYY-MM-DD (ISO format)
_PAT_NUMERIC_ISO = re.compile(
    r"(\d{4})-(\d{1,2})-(\d{1,2})"
)

# Common date suffixes in Marathi (e.g. जुलैला, जुलैच्या, जुलैतील, जुलैमध्ये, जुलै रोजी)
_MARATHI_DATE_SUFFIXES = r"(?:ला|ची|च्या|तील|मध्ये|मधील|रोजी)?"

# "20 July", "20th July", "20 Jul", "20 जुलै", "20 जुलैला", "20 जुलै 2026"
_PAT_DAY_MONTH = re.compile(
    rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({_ALL_MONTH_NAMES}){_MARATHI_DATE_SUFFIXES}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)

# "July 20", "July 20th", "July 20 2026"
_PAT_MONTH_DAY = re.compile(
    rf"({_ALL_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?{_MARATHI_DATE_SUFFIXES}(?:\s+(\d{{4}}))?",
    re.IGNORECASE,
)


def _resolve_month(name: str) -> Optional[int]:
    """Resolve a month name (English or Marathi) to its number."""
    lower = name.lower()
    return _ENGLISH_MONTHS.get(lower) or _MARATHI_MONTHS.get(name)


def extract_date(question: str) -> Optional[date]:
    """Extract a date from a user's question.

    Supports English, Marathi, and numeric date formats.
    Uses the current year as default when year is not specified.

    Args:
        question: The user's question string.

    Returns:
        A date object if a valid date is found, None otherwise.
    """
    # Normalize Marathi digits first (e.g. २० -> 20, २०२६ -> 2026)
    normalized = _normalize_marathi_digits(question)
    current_year = datetime.now().year

    # Try ISO format first: YYYY-MM-DD
    match = _PAT_NUMERIC_ISO.search(normalized)
    if match:
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            pass

    # Try DD/MM/YYYY or DD-MM-YYYY
    match = _PAT_NUMERIC_DMY.search(normalized)
    if match:
        try:
            return date(int(match.group(3)), int(match.group(2)), int(match.group(1)))
        except ValueError:
            pass

    # Try "20 July" / "20th Jul" / "20 जुलै" / "20 जुलै 2026"
    match = _PAT_DAY_MONTH.search(normalized)
    if match:
        month = _resolve_month(match.group(2))
        if month:
            year = int(match.group(3)) if match.group(3) else current_year
            try:
                return date(year, month, int(match.group(1)))
            except ValueError:
                pass

    # Try "July 20" / "July 20th" / "July 20 2026"
    match = _PAT_MONTH_DAY.search(normalized)
    if match:
        month = _resolve_month(match.group(1))
        if month:
            year = int(match.group(3)) if match.group(3) else current_year
            try:
                return date(year, month, int(match.group(2)))
            except ValueError:
                pass

    return None


def _strip_date_from_query(question: str) -> str:
    """Remove the date portion and generic question words from a query.

    Used when a question contains both a date and keywords
    (e.g. '20 July politics' -> 'politics').
    If only question fillers remain (e.g. '20 जुलैला काय घडलं?'),
    it returns empty string so date-only search is performed.
    """
    normalized = _normalize_marathi_digits(question)

    # Remove date patterns in order of specificity
    cleaned = _PAT_NUMERIC_ISO.sub("", normalized)
    cleaned = _PAT_NUMERIC_DMY.sub("", cleaned)
    cleaned = _PAT_DAY_MONTH.sub("", cleaned)
    cleaned = _PAT_MONTH_DAY.sub("", cleaned)

    # Strip generic Marathi & English question/filler words and punctuation
    # Handles Devanagari anusvara (\u0902), suffixes, and variations
    filler_pattern = (
        r"(काय|घड[लळ\w\u0900-\u0903]*|झा[लळ\w\u0900-\u0903]*|बातमी|बातम्या|अपडेट[सस्]*|"
        r"अप्डेट[सस्]*|वृत्त|माहिती|सांगा|\b(on|of|in|the|what|happened|news|updates|latest|cha|chya|la)\b|[?.,!:-])"
    )
    cleaned = re.sub(filler_pattern, "", cleaned, flags=re.IGNORECASE)

    # Clean up whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


# --- Truncation helper ---

def _truncate_content(articles: list[dict]) -> list[dict]:
    """Truncate article content to BODY_LIMIT characters without cutting mid-word."""
    for article in articles:
        content = article["content"] or ""
        truncated = " ".join(content.split())[:BODY_LIMIT]

        # Avoid cutting mid-word
        if len(truncated) < len(content) and " " in truncated:
            truncated = truncated[:truncated.rfind(" ")]

        article["content"] = truncated

    return articles


# --- Search functions ---

def _search_fulltext(query: str, limit: int = 3) -> list[dict]:
    """Search articles using MySQL FULLTEXT search.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.

    Returns:
        A list of article dicts. Returns empty list on failure.
    """
    sql = """
        SELECT
            p.title,
            p.content,
            c.name AS category,
            d.name AS district,
            p.createdAt,
            MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE) AS score
        FROM posts p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN district d ON p.district_id = d.id
        WHERE MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE)
          AND p.status = 'PUBLISHED'
        ORDER BY score DESC
        LIMIT %s
    """

    connection = get_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (query, query, limit))
            articles = cursor.fetchall()

        articles = _truncate_content(articles)
        logger.info("FULLTEXT search '%s' returned %d results", query[:50], len(articles))
        for article in articles:
            logger.info("- %s", article["title"])
        return articles

    except pymysql.Error as e:
        logger.error("FULLTEXT search failed: %s", e)
        return []
    finally:
        connection.close()


def search_by_date(date_value: date, limit: int = 10) -> list[dict]:
    """Retrieve articles published on a specific date.

    Args:
        date_value: The target date.
        limit: Maximum number of results to return.

    Returns:
        A list of article dicts. Returns empty list on failure.
    """
    sql = """
        SELECT
            p.title,
            p.content,
            c.name AS category,
            d.name AS district,
            p.createdAt,
            0 AS score
        FROM posts p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN district d ON p.district_id = d.id
        WHERE DATE(p.createdAt) = %s
          AND p.status = 'PUBLISHED'
        ORDER BY p.createdAt DESC
        LIMIT %s
    """

    connection = get_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (date_value, limit))
            articles = cursor.fetchall()

        articles = _truncate_content(articles)
        logger.info("Date search '%s' returned %d results", date_value, len(articles))
        for article in articles:
            logger.info("- %s", article["title"])
        return articles

    except pymysql.Error as e:
        logger.error("Date search failed: %s", e)
        return []
    finally:
        connection.close()


def _search_date_with_keywords(date_value: date, keywords: str, limit: int = 5) -> list[dict]:
    """Search articles by date AND FULLTEXT keywords.

    Used when the user's question contains both a date and additional
    keywords (e.g. '20 July politics' or '20 जुलै राजकारण').

    Args:
        date_value: The target date.
        keywords: The keyword string for FULLTEXT matching.
        limit: Maximum number of results to return.

    Returns:
        A list of article dicts ranked by relevance. Returns empty list on failure.
    """
    sql = """
        SELECT
            p.title,
            p.content,
            c.name AS category,
            d.name AS district,
            p.createdAt,
            MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE) AS score
        FROM posts p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN district d ON p.district_id = d.id
        WHERE DATE(p.createdAt) = %s
          AND MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE)
          AND p.status = 'PUBLISHED'
        ORDER BY score DESC
        LIMIT %s
    """

    connection = get_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (keywords, date_value, keywords, limit))
            articles = cursor.fetchall()

        articles = _truncate_content(articles)
        logger.info(
            "Date+keyword search '%s' on %s returned %d results",
            keywords[:50], date_value, len(articles),
        )
        for article in articles:
            logger.info("- %s", article["title"])
        return articles

    except pymysql.Error as e:
        logger.error("Date+keyword search failed: %s", e)
        return []
    finally:
        connection.close()


# --- Public API ---

def search_articles(query: str, limit: int = 3) -> list[dict]:
    """Search articles using date-aware retrieval with FULLTEXT fallback.

    Detection logic:
        1. If the question contains a date AND keywords -> date + FULLTEXT search
        2. If the question contains only a date -> date-only search
        3. Otherwise -> standard FULLTEXT search

    Args:
        query: The user's question string.
        limit: Maximum number of results to return.

    Returns:
        A list of article dicts with keys: title, content, category,
        district, createdAt, score. Returns empty list on failure.
    """
    detected_date = extract_date(query)

    if detected_date is not None:
        keywords = _strip_date_from_query(query)

        if keywords:
            # Date + keywords: filter by date, rank by FULLTEXT relevance
            logger.info("Detected date %s with keywords '%s'", detected_date, keywords[:50])
            return _search_date_with_keywords(detected_date, keywords, limit=limit)

        # Date only: return all articles from that date
        logger.info("Detected date-only query: %s", detected_date)
        return search_by_date(detected_date, limit=10)

    # No date detected: standard FULLTEXT search
    return _search_fulltext(query, limit=limit)