"""Database operations and connection management for MySQL Community 8.0."""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import pymysql
from dotenv import load_dotenv

from entity_normalizer import DistrictNormalizer

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


_DISTRICT_NORMALIZER = DistrictNormalizer()

# In-memory mapping of Canonical Marathi District Name -> English DB Name
_MARATHI_TO_ENGLISH_DISTRICTS: Dict[str, str] = {
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


def _get_district_id_map(cursor) -> Dict[str, int]:
    """Fetch current English district name -> district_id mapping from database."""
    cursor.execute("SELECT id, name FROM district")
    rows = cursor.fetchall()
    return {row["name"]: row["id"] for row in rows}


def insert_article(article: Dict[str, Any]) -> bool:
    """Insert a single article into the posts table with dynamic metadata resolution.

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
            # 1. Resolve dynamic district_id
            district_map = _get_district_id_map(cursor)
            text_sample = f"{article.get('title', '')} {(article.get('body', ''))[:600]}"
            norm_res = _DISTRICT_NORMALIZER.normalize_query(text_sample)

            detected_district_id = None
            if norm_res.matched_districts:
                canonical_marathi = norm_res.matched_districts[0].canonical_name
                english_name = _MARATHI_TO_ENGLISH_DISTRICTS.get(canonical_marathi)
                if english_name and english_name in district_map:
                    detected_district_id = district_map[english_name]

            cursor.execute(query, (
                article["title"],
                article["body"],
                False,                  # is_breaking
                1,                      # category_id (Politics default)
                0,                      # viewer_count
                "PUBLISHED",            # status
                detected_district_id,   # dynamic district_id
                1,                      # user_id
                published_at,           # createdAt
                published_at,           # updatedAt
            ))
        connection.commit()
        logger.info("Inserted article: '%s' (district_id=%s)", article["title"][:70], detected_district_id)
        return True
    except pymysql.err.IntegrityError:
        logger.debug("Article already exists: %s", article["title"][:80])
        return False
    except pymysql.Error as e:
        logger.error("DB error inserting article: %s", e)
        return False
    finally:
        connection.close()