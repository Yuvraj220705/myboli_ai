"""Transactional Migration Script to Repair District Metadata for Existing Articles.

Inspects all existing articles in the database, extracts the correct district
from title and content using DistrictNormalizer, ensures all districts exist in the
'district' table, updates posts.district_id transactionally, and logs all changes.
"""

import logging
import sys
import time
from pathlib import Path
from typing import Dict

# Reconfigure stdout for UTF-8 encoding
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to Python module path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

from db import get_connection
from entity_normalizer import DistrictNormalizer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("repair_district_metadata")

# Mapping of Canonical Marathi District Name -> English DB Name
MARATHI_TO_ENGLISH_DISTRICTS: Dict[str, str] = {
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


def sync_district_table(cursor) -> Dict[str, int]:
    """Ensure all 36 Maharashtra districts exist in the 'district' table.

    Returns:
        Dict[str, int]: Mapping of English District Name -> district_id.
    """
    cursor.execute("SELECT id, name FROM district")
    existing_rows = cursor.fetchall()
    district_map: Dict[str, int] = {row["name"]: row["id"] for row in existing_rows}

    inserted_count = 0
    for english_name in MARATHI_TO_ENGLISH_DISTRICTS.values():
        if english_name not in district_map:
            cursor.execute(
                "INSERT INTO district (name, createdAt, updatedAt) VALUES (%s, NOW(), NOW())",
                (english_name,)
            )
            district_map[english_name] = cursor.lastrowid
            inserted_count += 1

    logger.info("District table synced. Total districts: %d (New inserted: %d)", len(district_map), inserted_count)
    return district_map


def repair_article_districts():
    normalizer = DistrictNormalizer()
    conn = get_connection()
    conn.autocommit = False  # Enable transaction mode

    try:
        with conn.cursor() as cursor:
            # 1. Sync district table
            district_name_to_id = sync_district_table(cursor)

            # 2. Fetch all published posts
            cursor.execute("SELECT id, title, content, district_id FROM posts")
            posts = cursor.fetchall()
            logger.info("Starting district metadata migration across %d articles...", len(posts))

            updated_count = 0
            unassigned_count = 0
            stats_by_district: Dict[str, int] = {}

            for post in posts:
                post_id = post["id"]
                title = post["title"] or ""
                body = (post["content"] or "")[:600]
                text_sample = f"{title} {body}"

                # Re-extract district using entity normalizer
                result = normalizer.normalize_query(text_sample)

                target_district_id = None
                matched_district_name = None

                if result.matched_districts:
                    canonical_marathi = result.matched_districts[0].canonical_name
                    english_name = MARATHI_TO_ENGLISH_DISTRICTS.get(canonical_marathi)
                    if english_name and english_name in district_name_to_id:
                        target_district_id = district_name_to_id[english_name]
                        matched_district_name = english_name

                # Perform update if district_id differs
                if target_district_id != post["district_id"]:
                    cursor.execute(
                        "UPDATE posts SET district_id = %s WHERE id = %s",
                        (target_district_id, post_id)
                    )
                    updated_count += 1

                if matched_district_name:
                    stats_by_district[matched_district_name] = stats_by_district.get(matched_district_name, 0) + 1
                else:
                    unassigned_count += 1

        conn.commit()  # Commit transaction safely
        logger.info("✅ TRANSACTION COMMITTED SUCCESSFULLY!")
        logger.info("Migrated/re-assigned district_id for %d articles.", updated_count)
        logger.info("Unassigned (General/State news): %d articles.", unassigned_count)
        logger.info("Final District Allocation Summary:")
        for dist_name, count in sorted(stats_by_district.items(), key=lambda x: x[1], reverse=True):
            logger.info("  - %s: %d articles", dist_name, count)

    except Exception as e:
        conn.rollback()
        logger.error("❌ TRANSACTION ROLLED BACK due to error: %s", e)
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    t0 = time.time()
    logger.info("==================================================")
    logger.info(" SPRINT MIGRATION: REPAIR DISTRICT METADATA ")
    logger.info("==================================================")
    repair_article_districts()
    logger.info("Elapsed Migration Time: %.2f seconds", time.time() - t0)
    logger.info("==================================================")
