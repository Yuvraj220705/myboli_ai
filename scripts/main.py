"""Multi-category article scraping and database ingestion pipeline for Myboli AI.

Scrapes articles from multiple Maharashtra Times category URLs, deduplicates links,
prevents database duplication, handles failures gracefully, displays real-time progress,
and saves reports to `failed_urls.txt` and `scrape_report.json`.
"""

import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Set

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from collect_links import BASE_URL, collect_links, discover_category_urls
from db import get_connection, insert_article
from scrape_article import scrape_article

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# --- Constants ---

REQUEST_DELAY_SECONDS: float = 0.5
FAILED_URLS_FILE: str = "failed_urls.txt"
SCRAPE_REPORT_FILE: str = "scrape_report.json"
TARGET_INSERTIONS_DEFAULT: int = 1100

# Curated list of default category URLs across Maharashtra districts and news sections
CATEGORY_URLS: List[str] = [
    f"{BASE_URL}/maharashtra/sindhudurg/articlelist/81397428.cms",
    f"{BASE_URL}/latest-news/articlelist/75401897.cms",
    f"{BASE_URL}/maharashtra/akola/articlelist/81916873.cms",
    f"{BASE_URL}/crime-news/articlelist/74933788.cms",
    f"{BASE_URL}/business/articlelist/47416711.cms",
    f"{BASE_URL}/sports/articlelist/2429056.cms",
    f"{BASE_URL}/lifestyle-news/articlelist/2429025.cms",
    f"{BASE_URL}/agriculture/articlelist/93931952.cms",
    f"{BASE_URL}/maharashtra/navi-mumbai/articlelist/47583234.cms",
    f"{BASE_URL}/maharashtra/sangli/articlelist/84964682.cms",
    f"{BASE_URL}/government-policy/articlelist/87712526.cms",
    f"{BASE_URL}/maharashtra/pune-news/articlelist/2429654.cms",
    f"{BASE_URL}/gadget-news/articlelist/2499221.cms",
    f"{BASE_URL}/editorial/articlelist/2429614.cms",
    f"{BASE_URL}/maharashtra/latur/articlelist/81984728.cms",
    f"{BASE_URL}/maharashtra/chandrapur/articlelist/84338193.cms",
    f"{BASE_URL}/maharashtra/bhandara/articlelist/87273761.cms",
    f"{BASE_URL}/sports/cricket/articlelist/2429623.cms",
    f"{BASE_URL}/entertainment/entertainment-news/bollywood-news/articlelist/73141837.cms",
    f"{BASE_URL}/maharashtra/kolhapur/articlelist/81397425.cms",
    f"{BASE_URL}/maharashtra/ratnagiri/articlelist/81397430.cms",
]


@dataclass
class IngestionStats:
    """Records real-time metrics for the scraping pipeline."""
    categories_processed: int = 0
    total_links_discovered: int = 0
    articles_scraped: int = 0
    articles_inserted: int = 0
    duplicates_skipped: int = 0
    failures: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    failed_urls: List[str] = field(default_factory=list)

    @property
    def execution_time_seconds(self) -> float:
        """Calculate total elapsed execution time in seconds."""
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def formatted_execution_time(self) -> str:
        """Format elapsed execution time as hh:mm:ss or mm:ss."""
        total_sec = int(self.execution_time_seconds)
        minutes, seconds = divmod(total_sec, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
        return f"{minutes:02d}m {seconds:02d}s"


# --- Helper Functions ---

def fetch_existing_titles() -> Set[str]:
    """Fetch normalized article titles existing in database to prevent duplicates.

    Returns:
        Set[str]: Set of existing article titles.
    """
    try:
        connection = get_connection()
    except Exception as e:
        logger.error("Database connection failure while fetching existing titles: %s", e)
        return set()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT title FROM posts WHERE title IS NOT NULL")
            rows = cursor.fetchall()
            titles = {row["title"].strip() for row in rows if row.get("title")}
            logger.info("Loaded %d existing article titles from database cache", len(titles))
            return titles
    except Exception as e:
        logger.error("Error fetching existing titles from database: %s", e)
        return set()
    finally:
        try:
            connection.close()
        except Exception:
            pass


def save_failed_urls(failed_urls: List[str], filepath: str = FAILED_URLS_FILE) -> None:
    """Save failed article URLs to a text file.

    Args:
        failed_urls: List of URLs that failed during scraping or database insertion.
        filepath: Path to the target text file.
    """
    try:
        Path(filepath).write_text("\n".join(failed_urls), encoding="utf-8")
        logger.info("Saved %d failed URLs to %s", len(failed_urls), filepath)
    except IOError as e:
        logger.error("Failed to write to %s: %s", filepath, e)


def save_scrape_report(stats: IngestionStats, filepath: str = SCRAPE_REPORT_FILE) -> None:
    """Save execution statistics and summary report to a JSON file.

    Args:
        stats: IngestionStats dataclass instance containing execution metrics.
        filepath: Path to the output JSON file.
    """
    report_data = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "categories_processed": stats.categories_processed,
        "total_links_discovered": stats.total_links_discovered,
        "articles_scraped": stats.articles_scraped,
        "articles_inserted": stats.articles_inserted,
        "duplicates_skipped": stats.duplicates_skipped,
        "failures": stats.failures,
        "execution_time_seconds": round(stats.execution_time_seconds, 2),
        "execution_time_formatted": stats.formatted_execution_time,
        "failed_urls_count": len(stats.failed_urls),
        "failed_urls": stats.failed_urls,
    }

    try:
        Path(filepath).write_text(json.dumps(report_data, indent=4, ensure_ascii=False), encoding="utf-8")
        logger.info("Saved scraping report to %s", filepath)
    except IOError as e:
        logger.error("Failed to write scrape report to %s: %s", filepath, e)


def print_summary(stats: IngestionStats) -> None:
    """Print clean formatted execution summary.

    Args:
        stats: IngestionStats dataclass instance.
    """
    print("\n" + "=" * 36)
    print("SCRAPING COMPLETE")
    print("=" * 36)
    print(f"Categories processed: {stats.categories_processed}")
    print(f"Total links discovered: {stats.total_links_discovered}")
    print(f"Articles scraped: {stats.articles_scraped}")
    print(f"Articles inserted: {stats.articles_inserted}")
    print(f"Duplicates skipped: {stats.duplicates_skipped}")
    print(f"Failures: {stats.failures}")
    print(f"Execution time: {stats.formatted_execution_time}")
    print("=" * 36 + "\n")


def calculate_eta(processed: int, total: int, start_time: float) -> str:
    """Calculate estimated time remaining (ETA) for processing.

    Args:
        processed: Count of processed items.
        total: Total items to process.
        start_time: Timestamp when processing started.

    Returns:
        Formatted ETA string (e.g. '02m 15s' or 'Calculating...').
    """
    if processed == 0 or total <= processed:
        return "00m 00s"

    elapsed = time.time() - start_time
    avg_per_item = elapsed / processed
    remaining_sec = int((total - processed) * avg_per_item)

    mins, secs = divmod(remaining_sec, 60)
    hrs, mins = divmod(mins, 60)
    if hrs > 0:
        return f"{hrs:02d}h {mins:02d}m {secs:02d}s"
    return f"{mins:02d}m {secs:02d}s"


# --- Core Pipeline Execution ---

def run_ingestion_pipeline(
    category_urls: Optional[List[str]] = None,
    auto_discover: bool = True,
    target_insertions: int = TARGET_INSERTIONS_DEFAULT,
) -> IngestionStats:
    """Execute the multi-category scraping and ingestion pipeline.

    Args:
        category_urls: Optional explicit category URLs list.
        auto_discover: If True, automatically discover categories from site homepage.
        target_insertions: Maximum number of articles to insert into DB before stopping.

    Returns:
        IngestionStats: Structured summary metrics.
    """
    stats = IngestionStats()

    # 1. Build category list
    urls_to_process: List[str] = list(category_urls) if category_urls else list(CATEGORY_URLS)

    if auto_discover:
        logger.info("Discovering additional category URLs from homepage...")
        discovered = discover_category_urls()
        for url in discovered:
            if url not in urls_to_process:
                urls_to_process.append(url)

    stats.categories_processed = len(urls_to_process)
    logger.info("Starting ingestion across %d categories (target insertions: %d)", stats.categories_processed, target_insertions)

    # 2. Pre-fetch existing database titles
    existing_titles = fetch_existing_titles()
    visited_urls: Set[str] = set()

    # 3. Discover and deduplicate all article links first
    all_discovered_links: List[str] = []

    for cat_idx, cat_url in enumerate(urls_to_process, start=1):
        logger.info("[%d/%d] Collecting links from category: %s", cat_idx, stats.categories_processed, cat_url)
        try:
            links = collect_links(cat_url)
            for link in links:
                if link not in visited_urls:
                    visited_urls.add(link)
                    all_discovered_links.append(link)
        except Exception as e:
            logger.error("Error collecting links from category %s: %s", cat_url, e)

    stats.total_links_discovered = len(all_discovered_links)
    logger.info("Total unique article links discovered: %d", stats.total_links_discovered)

    # 4. Scrape and insert articles sequentially with live progress and ETA
    total_articles = stats.total_links_discovered
    process_start_time = time.time()

    for idx, link in enumerate(all_discovered_links, start=1):
        if len(existing_titles) >= target_insertions:
            logger.info("Target total database articles limit reached (%d). Stopping pipeline.", target_insertions)
            break

        eta_str = calculate_eta(idx - 1, total_articles, process_start_time)

        # Live Progress Display
        print(
            f"\r[Progress {idx}/{total_articles} | Scraped: {stats.articles_scraped} | "
            f"Inserted: {stats.articles_inserted} | Duplicates: {stats.duplicates_skipped} | "
            f"Failures: {stats.failures} | ETA: {eta_str}]",
            end="",
            flush=True,
        )

        logger.info(
            "\n[Article %d/%d] Scraping: %s (ETA: %s)",
            idx, total_articles, link[:75], eta_str
        )

        # Scrape article
        try:
            article = scrape_article(link)
        except Exception as e:
            logger.error("Error scraping article %s: %s", link, e)
            stats.failures += 1
            stats.failed_urls.append(link)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        if article is None or not article.get("title") or not article.get("body"):
            stats.failures += 1
            stats.failed_urls.append(link)
            logger.warning("Scraping returned invalid/empty data for: %s", link[:75])
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        stats.articles_scraped += 1
        title = article["title"].strip()

        # Check existing title duplicate
        if title in existing_titles:
            stats.duplicates_skipped += 1
            logger.info("Duplicate article title skipped: '%s'", title[:60])
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        # DB Insertion
        try:
            inserted = insert_article(article)
            if inserted:
                stats.articles_inserted += 1
                existing_titles.add(title)
                logger.info("-> Successfully inserted [%d/%d]: '%s'", stats.articles_inserted, target_insertions, title[:60])
            else:
                stats.duplicates_skipped += 1
                logger.info("Duplicate on DB insert: '%s'", title[:60])
        except Exception as e:
            logger.error("DB insertion error for '%s': %s", title[:60], e)
            stats.failures += 1
            stats.failed_urls.append(link)

        time.sleep(REQUEST_DELAY_SECONDS)

    stats.end_time = time.time()

    # Save output artifacts
    save_failed_urls(stats.failed_urls)
    save_scrape_report(stats)

    # Print final summary
    print_summary(stats)

    return stats


if __name__ == "__main__":
    run_ingestion_pipeline(auto_discover=True, target_insertions=1100)