"""Retrieves articles from MySQL using FULLTEXT search with date-aware retrieval."""

import logging
from datetime import date

import pymysql

from date_parser import extract_date, strip_date_from_query
from db import get_connection

logger = logging.getLogger(__name__)

BODY_LIMIT = 1500


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
        keywords = strip_date_from_query(query)

        if keywords:
            # Date + keywords: filter by date, rank by FULLTEXT relevance
            logger.info("Detected date %s with keywords '%s'", detected_date, keywords[:50])
            return _search_date_with_keywords(detected_date, keywords, limit=limit)

        # Date only: return all articles from that date
        logger.info("Detected date-only query: %s", detected_date)
        return search_by_date(detected_date, limit=10)

    # No date detected: standard FULLTEXT search
    return _search_fulltext(query, limit=limit)