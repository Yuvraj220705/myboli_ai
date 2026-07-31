"""Retrieves published articles from MySQL using FULLTEXT search and optional metadata filters."""

import logging
from datetime import date
from typing import Any, Dict, List, Optional

import pymysql

from date_parser import extract_date, strip_date_from_query
from db import get_connection
from query_processor import process_query

logger = logging.getLogger(__name__)

BODY_LIMIT = 1500


def _truncate_content(articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Truncate article content to BODY_LIMIT characters without cutting mid-word."""
    for article in articles:
        content = article.get("content") or ""
        truncated = " ".join(content.split())[:BODY_LIMIT]

        # Avoid cutting mid-word
        if len(truncated) < len(content) and " " in truncated:
            truncated = truncated[:truncated.rfind(" ")]

        article["content"] = truncated

    return articles


def _execute_query(
    search_text: str,
    target_date: Optional[date] = None,
    target_category: Optional[str] = None,
    target_district: Optional[str] = None,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Execute dynamic SQL query on posts table using FULLTEXT search and filters.

    Args:
        search_text: Text string for FULLTEXT MATCH AGAINST logic.
        target_date: Optional date filter.
        target_category: Optional category filter.
        target_district: Optional district filter.
        limit: Maximum number of articles to return.

    Returns:
        List[Dict[str, Any]]: Retrieved articles with keys (id, title, content,
        category, district, createdAt, score). Empty list on failure or no matches.
    """
    where_clauses = ["p.status = 'PUBLISHED'"]
    params: List[Any] = []

    has_fulltext = bool(search_text and search_text.strip())

    if has_fulltext:
        select_score = "MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE) AS score"
        params.append(search_text.strip())
        where_clauses.append("MATCH(p.title, p.content) AGAINST(%s IN NATURAL LANGUAGE MODE)")
        params.append(search_text.strip())
    else:
        select_score = "0.0 AS score"

    if target_date:
        where_clauses.append("DATE(p.createdAt) = %s")
        params.append(target_date)

    if target_category:
        where_clauses.append("(LOWER(c.name) = LOWER(%s) OR c.name LIKE %s)")
        params.extend([target_category, f"%{target_category}%"])

    if target_district:
        where_clauses.append("(LOWER(d.name) = LOWER(%s) OR d.name LIKE %s)")
        params.extend([target_district, f"%{target_district}%"])

    where_sql = " AND ".join(where_clauses)
    order_sql = "score DESC, p.createdAt DESC" if has_fulltext else "p.createdAt DESC"

    sql = f"""
        SELECT
            p.id,
            p.title,
            p.content,
            c.name AS category,
            d.name AS district,
            p.createdAt,
            {select_score}
        FROM posts p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN district d ON p.district_id = d.id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT %s
    """
    params.append(limit)

    try:
        connection = get_connection()
    except Exception as e:
        logger.error("Failed to connect to database in retriever: %s", e)
        return []

    try:
        with connection.cursor() as cursor:
            cursor.execute(sql, tuple(params))
            results = cursor.fetchall()
            return list(results) if results else []
    except pymysql.Error as e:
        logger.error("Database retrieval query failed: %s", e)
        return []
    finally:
        try:
            connection.close()
        except Exception:
            pass


def search_articles(
    query: str,
    top_k: int = 5,
    date_filter: Optional[date] = None,
    category_filter: Optional[str] = None,
    district_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-K published articles using FULLTEXT search and optional metadata filtering.

    Args:
        query: User question string.
        top_k: Top-K limit of articles to retrieve (default: 5).
        date_filter: Optional explicit date filter.
        category_filter: Optional explicit category filter.
        district_filter: Optional explicit district filter.

    Returns:
        List[Dict[str, Any]]: List of retrieved article dicts including article 'id'.
        Returns empty list if no matching published articles are found or on failure.
    """
    if not query or not query.strip():
        return []

    # Process query to detect metadata (date, category, district) and clean text
    query_info = process_query(query)

    effective_date = date_filter or query_info.date
    effective_category = category_filter or query_info.category
    effective_district = district_filter or query_info.district
    clean_query = query_info.clean_query.strip()

    logger.info(
        "Searching articles: query='%s', clean_text='%s', date=%s, category=%s, district=%s, top_k=%d",
        query[:50], clean_query[:50], effective_date, effective_category, effective_district, top_k
    )

    # 0. Check for latest news intent (e.g. "आज काय घडलं", "ताज्या बातम्या")
    if query_info.is_latest_news:
        logger.info("Latest news intent detected. Retrieving newest articles by createdAt DESC.")
        articles = _execute_query(
            search_text="",
            target_date=effective_date,
            target_category=effective_category,
            target_district=effective_district,
            limit=top_k,
        )
        articles = _truncate_content(articles)
        logger.info("Retriever found %d published articles for latest news request", len(articles))
        return articles

    # 1. First attempt: search using clean text + metadata filters
    articles = _execute_query(
        search_text=clean_query,
        target_date=effective_date,
        target_category=effective_category,
        target_district=effective_district,
        limit=top_k,
    )

    # 2. Fallback attempt 1: if text+metadata yields nothing, search with metadata filters only
    if not articles and (effective_date or effective_category or effective_district) and clean_query:
        logger.info("Retrying query with metadata filters only.")
        articles = _execute_query(
            search_text="",
            target_date=effective_date,
            target_category=effective_category,
            target_district=effective_district,
            limit=top_k,
        )

    # 3. Fallback attempt 2: if metadata search yields nothing, try FULLTEXT on original query
    if not articles and (effective_date or effective_category or effective_district):
        fallback_text = clean_query if clean_query else query.strip()
        logger.info("Retrying query with raw FULLTEXT search: '%s'", fallback_text[:50])
        articles = _execute_query(
            search_text=fallback_text,
            target_date=None,
            target_category=None,
            target_district=None,
            limit=top_k,
        )

    articles = _truncate_content(articles)
    logger.info("Retriever found %d published articles", len(articles))
    return articles