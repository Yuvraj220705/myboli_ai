"""Collects article links from a Maharashtra Times category page."""

import logging

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://maharashtratimes.com"
REQUEST_TIMEOUT = 10
DEFAULT_HEADERS = {"User-Agent": "Mozilla/5.0"}


def collect_links(url: str) -> list[str]:
    """Scrape article links from a category listing page.

    Args:
        url: The category page URL to scrape.

    Returns:
        A list of unique article URLs found on the page.
    """
    try:
        response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error("Failed to fetch page %s: %s", url, e)
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    links = set()

    for tag in soup.find_all("a", href=True):
        href = tag["href"]

        if "/articleshow/" not in href:
            continue

        if href.startswith("/"):
            href = BASE_URL + href

        links.add(href)

    logger.info("Collected %d article links from %s", len(links), url)
    return list(links)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    url = f"{BASE_URL}/maharashtra/sindhudurg/articlelist/81397428.cms"

    links = collect_links(url)

    print(f"Found {len(links)} article links:\n")

    for link in links:
        print(link)