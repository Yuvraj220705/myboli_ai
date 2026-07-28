"""Extracts article data from Maharashtra Times article pages via JSON-LD."""

import json
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


def scrape_article(url: str) -> Optional[dict]:
    """Extract article data from a news article page using JSON-LD.

    Args:
        url: The article URL to scrape.

    Returns:
        A dict with keys: title, body, published_at, url.
        Returns None if the article cannot be extracted.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch article %s: %s", url, e)
        return None

    soup = BeautifulSoup(response.text, "html.parser")
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        try:
            data = json.loads(script.string or "")
        except json.JSONDecodeError as e:
            logger.debug("Invalid JSON-LD in %s: %s", url, e)
            continue

        if not isinstance(data, dict) or data.get("@type") != "NewsArticle":
            continue

        body = data.get("articleBody", "")
        body = " ".join(body.split())

        article = {
            "title": data.get("headline", ""),
            "body": body,
            "published_at": data.get("datePublished", ""),
            "url": url,
        }

        logger.info("Scraped article: %s", article["title"][:80])
        return article

    logger.warning("No NewsArticle JSON-LD found at %s", url)
    return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_url = (
        "https://maharashtratimes.com/maharashtra/sindhudurg/"
        "firoz-baba-linked-in-shiv-sena-vinayak-raut-case-notice-"
        "also-served-to-eknath-shinde-shiv-sena-sanju-parab/"
        "articleshow/132460515.cms"
    )

    article = scrape_article(test_url)

    if article:
        print("Title:\n", article["title"])
        print("\nPublished At:\n", article["published_at"])
        print("\nURL:\n", article["url"])
        print("\nBody:\n")
        print(article["body"][:300])