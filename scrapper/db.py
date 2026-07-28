"""Database operations for article storage."""

import logging
import os
from datetime import datetime
from typing import Optional

import pymysql
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def get_connection() -> pymysql.Connection:
    """Create a new database connection from environment variables.

    Returns:
        A pymysql Connection object.

    Raises:
        pymysql.Error: If the connection cannot be established.
    """
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "maayboli_client"),
        charset="utf8mb4",
    )


def insert_article(article: dict) -> bool:
    """Insert a single article into the database.

    Args:
        article: Dict with keys: title, body, url, published_at.

    Returns:
        True if inserted successfully, False otherwise.
    """
    # NOTE: article["url"] is not inserted — the client's posts table has no
    # article_url column yet. If the schema is updated, add it here.

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

    connection = get_connection()
    try:
        with connection.cursor() as cursor:
            # DEV DEFAULTS: category_id, district_id, and user_id are hardcoded
            # to 1 for local development. In production, the client's CMS manages
            # these foreign key relationships with valid referenced records.
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
                published_at,   # updatedAt (same as createdAt on first insert)
            ))
        connection.commit()
        logger.info("Inserted: %s", article["title"][:80])
        return True
    except pymysql.err.IntegrityError:
        logger.debug("Article already exists: %s", article["title"][:80])
        return False
    except pymysql.Error as e:
        logger.error("DB error inserting article: %s", e)
        return False
    finally:
        connection.close()