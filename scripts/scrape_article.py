"""Extracts article title, content, publication timestamp, and URL from news pages."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _extract_from_json_ld(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    """Attempt to extract article details using structured JSON-LD data.

    Args:
        soup: Parsed BeautifulSoup document.
        url: Article source URL.

    Returns:
        Optional[Dict[str, Any]]: Article dict if found, None otherwise.
    """
    scripts = soup.find_all("script", type="application/ld+json")

    for script in scripts:
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        # Single JSON-LD object vs list of JSON-LD objects
        items = data if isinstance(data, list) else [data]

        for item in items:
            if not isinstance(item, dict):
                continue

            item_type = item.get("@type")
            if item_type in ["NewsArticle", "Article", "BlogPosting"]:
                title = item.get("headline") or item.get("name") or ""
                body = item.get("articleBody") or item.get("description") or ""
                published_at = item.get("datePublished") or item.get("dateCreated") or ""

                title = " ".join(title.split())
                body = " ".join(body.split())

                if title and body:
                    return {
                        "title": title,
                        "body": body,
                        "published_at": published_at or datetime.now().isoformat(),
                        "url": url,
                    }

    return None


def _extract_from_html_fallback(soup: BeautifulSoup, url: str) -> Optional[Dict[str, Any]]:
    """Fallback article extraction using standard HTML tag hierarchy.

    Args:
        soup: Parsed BeautifulSoup document.
        url: Article source URL.

    Returns:
        Optional[Dict[str, Any]]: Extracted article dict if title and body exist, None otherwise.
    """
    title_tag = soup.find("h1") or soup.find("title")
    title = " ".join(title_tag.text.split()) if title_tag else ""

    # Look for common article content containers
    body_container = (
        soup.find("div", class_="article-body")
        or soup.find("article")
        or soup.find("div", class_="main-content")
    )

    paragraphs = body_container.find_all("p") if body_container else soup.find_all("p")
    body_text = " ".join(" ".join(p.text.split()) for p in paragraphs if p.text.strip())

    if title and len(body_text) > 50:
        return {
            "title": title,
            "body": body_text,
            "published_at": datetime.now().isoformat(),
            "url": url,
        }

    return None


def scrape_article(url: str) -> Optional[Dict[str, Any]]:
    """Extract article headline, content, publication timestamp, and URL.

    Args:
        url: The article URL to fetch and parse.

    Returns:
        Optional[Dict[str, Any]]: Article dict containing (title, body, published_at, url),
        or None if parsing failed or required fields are missing.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch article URL %s: %s", url, e)
        return None

    try:
        soup = BeautifulSoup(response.text, "html.parser")

        # 1. Try structured JSON-LD extraction first
        article = _extract_from_json_ld(soup, url)
        if article:
            logger.info("Scraped article (JSON-LD): '%s'", article["title"][:70])
            return article

        # 2. Fallback to HTML meta / tag extraction
        article = _extract_from_html_fallback(soup, url)
        if article:
            logger.info("Scraped article (HTML Fallback): '%s'", article["title"][:70])
            return article

        logger.warning("Could not extract article content from %s", url)
        return None

    except Exception as e:
        logger.error("Error parsing article %s: %s", url, e, exc_info=True)
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_url = (
        "https://maharashtratimes.com/maharashtra/sindhudurg/"
        "firoz-baba-linked-in-shiv-sena-vinayak-raut-case-notice-"
        "also-served-to-eknath-shinde-shiv-sena-sanju-parab/"
        "articleshow/132460515.cms"
    )

    art = scrape_article(test_url)
    if art:
        print("Title:\n", art["title"])
        print("\nPublished At:\n", art["published_at"])
        print("\nURL:\n", art["url"])
        print("\nBody Preview:\n", art["body"][:200])