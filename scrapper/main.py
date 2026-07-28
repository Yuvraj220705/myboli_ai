"""Development utility for scraping and populating the local database.

Not used in production. The production chatbot reads directly
from the client's CMS database.
"""
import logging
import time

from collect_links import collect_links
from scrape_article import scrape_article
from db import insert_article

logger = logging.getLogger(__name__)

CATEGORY_URL = "https://maharashtratimes.com/maharashtra/sindhudurg/articlelist/81397428.cms"
REQUEST_DELAY_SECONDS = 1


def run_pipeline(url: str) -> dict:
    """Run the full scrape-and-store pipeline for a category URL.

    Args:
        url: The category page URL to scrape.

    Returns:
        A summary dict with counts: total, scraped, inserted, failed.
    """
    links = collect_links(url)
    logger.info("Found %d article links", len(links))

    stats = {"total": len(links), "scraped": 0, "inserted": 0, "failed": 0}

    for i, link in enumerate(links, start=1):
        logger.info("[%d/%d] Processing: %s", i, stats["total"], link[:80])

        try:
            article = scrape_article(link)

            if article is None:
                stats["failed"] += 1
                continue

            stats["scraped"] += 1

            if insert_article(article):
                stats["inserted"] += 1

        except Exception as e:
            logger.error("Unexpected error processing %s: %s", link, e)
            stats["failed"] += 1

        # Be polite — don't hammer the server
        time.sleep(REQUEST_DELAY_SECONDS)

    logger.info("Pipeline complete: %s", stats)
    return stats


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run_pipeline(CATEGORY_URL)