"""Collects article links from Maharashtra Times category pages."""

import logging
from typing import Dict, List, Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://maharashtratimes.com"
REQUEST_TIMEOUT = 10
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def collect_links(url: str) -> List[str]:
    """Scrape unique article links from a single category listing page.

    Args:
        url: The category page URL to scrape.

    Returns:
        List[str]: A list of absolute article URLs found on the page.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch category page %s: %s", url, e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links: Set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        # Only extract valid articleshow news URLs
        if "/articleshow/" not in href:
            continue

        # Skip photo galleries or video-only player pages
        if "/photogallery/" in href or "/videopolitshow/" in href:
            continue

        full_url = urljoin(BASE_URL, href)
        links.add(full_url)

    logger.info("Collected %d article links from %s", len(links), url)
    return list(links)


def discover_category_urls(base_url: str = BASE_URL) -> List[str]:
    """Discover category listing URLs (articlelist) from the main website.

    Args:
        base_url: Base site URL to discover categories from.

    Returns:
        List[str]: Discovered category articlelist URLs.
    """
    try:
        response = requests.get(base_url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to discover categories from %s: %s", base_url, e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    category_urls: Set[str] = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if "articlelist" in href and not any(k in href for k in ["photogallery", "video", "photoarticlelist"]):
            category_urls.add(urljoin(BASE_URL, href))

    logger.info("Discovered %d category URLs from homepage", len(category_urls))
    return list(category_urls)


def collect_links_from_multiple_categories(category_urls: List[str]) -> Dict[str, List[str]]:
    """Collect article links from a list of category URLs.

    Args:
        category_urls: List of category URLs to scrape.

    Returns:
        Dict[str, List[str]]: Mapping of category URL to list of article URLs.
    """
    results: Dict[str, List[str]] = {}

    for i, cat_url in enumerate(category_urls, start=1):
        logger.info("[%d/%d] Fetching category links: %s", i, len(category_urls), cat_url)
        links = collect_links(cat_url)
        results[cat_url] = links

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    sample_url = f"{BASE_URL}/maharashtra/sindhudurg/articlelist/81397428.cms"
    links = collect_links(sample_url)

    print(f"Found {len(links)} article links:\n")
    for link in links[:5]:
        print(link)