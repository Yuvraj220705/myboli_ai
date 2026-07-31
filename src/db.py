"""Database operations and connection management for MySQL Community 8.0."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import pymysql
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_connection() -> pymysql.Connection:
    """Create and return a new MySQL database connection using environment variables.

    Returns:
        pymysql.Connection: Active database connection with DictCursor.

    Raises:
        pymysql.Error: If the database connection cannot be established.
    """
    try:
        return pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            database=os.getenv("DB_NAME", "maayboli_client"),
            port=int(os.getenv("DB_PORT", "3306")),
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
    except pymysql.Error as e:
        logger.error("Database connection failure: %s", e)
        raise


def insert_article(article: Dict[str, Any]) -> bool:
    """Insert a single article into the posts table.

    Args:
        article: Dict with keys: title, body, url, published_at.

    Returns:
        bool: True if inserted successfully, False otherwise.
    """
    query = """
        INSERT INTO posts
            (title, content, is_breaking, category_id, viewer_count,
             status, district_id, user_id, createdAt, updatedAt)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """

    try:
        published_at = datetime.fromisoformat(
            article["published_at"]
        ).replace(tzinfo=None)
    except (ValueError, KeyError) as e:
        logger.error("Invalid published_at in article '%s': %s", article.get("title", "?"), e)
        return False

    try:
        connection = get_connection()
    except pymysql.Error:
        return False

    try:
        with connection.cursor() as cursor:
            cursor.execute(query, (
                article["title"],
                article["body"],
                False,          # is_breaking
                1,              # category_id
                0,              # viewer_count
                "PUBLISHED",    # status
                1,              # district_id
                1,              # user_id
                published_at,   # createdAt
                published_at,   # updatedAt
            ))
        connection.commit()
        logger.info("Inserted article: %s", article["title"][:80])
        return True
    except pymysql.err.IntegrityError:
        logger.debug("Article already exists: %s", article["title"][:80])
        return False
    except pymysql.Error as e:
        logger.error("DB error inserting article: %s", e)
        return False
    finally:
        connection.close()