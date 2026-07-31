# Myboli AI — Code Review (Part 1 of 3)

## Project Overview

| File | Purpose | Lines |
|---|---|---|
| `collect_links.py` | Scrapes article links from category page | 47 |
| `scrape_article.py` | Extracts article data from JSON-LD | 55 |
| `db.py` | MySQL insert logic | 47 |
| `retriever.py` | FULLTEXT search | 46 |
| `gemini_service.py` | Builds context + Gemini call | 85 |
| `main.py` | Orchestrates scrape pipeline | 22 |
| `test*.py` | Ad-hoc test scripts | ~59 |

---

## 1. Folder Structure Review

**Current:**
```
myboli_ai/
├── .env
├── requirements.txt
├── list_models.py          ← utility, not part of app
└── scrapper/
    ├── collect_links.py
    ├── scrape_article.py
    ├── db.py
    ├── retriever.py
    ├── gemini_service.py
    ├── main.py
    ├── test.py / test_*.py
    └── requirements.txt    ← duplicate, unclear which is canonical
```

### Issues Found

| # | Issue | Severity |
|---|---|---|
| 1 | Folder name `scrapper` is a typo — should be `scraper` | **[SHOULD]** |
| 2 | Two `requirements.txt` files (root + scrapper/) — confusing | **[MUST]** |
| 3 | Root `.env` but code runs from `scrapper/` — `load_dotenv()` may fail to find `.env` depending on CWD | **[MUST]** |
| 4 | No `.gitignore` — `.env`, `.venv`, `__pycache__` could be committed | **[MUST]** |
| 5 | `list_models.py` and `test.py` are dev utilities mixed with production code | **[SHOULD]** |
| 6 | No `__init__.py` — `scrapper/` is not a proper Python package (works now but breaks with Flask) | **[MUST]** |

### Recommended Structure (minimal changes)

```
myboli_ai/
├── .env
├── .gitignore              ← NEW
├── requirements.txt        ← single source of truth
├── scraper/                ← fix typo
│   ├── __init__.py         ← NEW (can be empty)
│   ├── collect_links.py
│   ├── scrape_article.py
│   ├── db.py
│   ├── retriever.py
│   ├── gemini_service.py
│   └── main.py
└── tests/                  ← NEW: separate test files
    ├── test_search.py
    ├── test_context.py
    └── test_gemini.py
```

---

## 2. File Review: `collect_links.py`

### What's Good
- Clean, single-responsibility function
- Uses `timeout=10` on requests
- Uses `set()` to deduplicate links
- Has a `__main__` block for standalone testing

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | No exception handling for `requests.get()` — `ConnectionError`, `Timeout` will crash | Exception Handling | **[MUST]** |
| 2 | Hardcoded domain `"https://maharashtratimes.com"` — magic string | Readability | **[SHOULD]** |
| 3 | `User-Agent: "Mozilla/5.0"` is repeated in `scrape_article.py` too | DRY / Code Duplication | **[SHOULD]** |
| 4 | No docstring | Readability | **[SHOULD]** |
| 5 | No type hints | Python Best Practices | **[SHOULD]** |
| 6 | No logging — `print()` is not suitable for production | Logging | **[MUST]** |
| 7 | No retry on transient network failures | Production Readiness | **[SHOULD]** |

### Improved Version

```python
"""Collects article links from a Maharashtra Times category page."""

import logging
from typing import Optional

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
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| `requests.RequestException` catch | Prevents crash on DNS failures, timeouts, connection resets |
| `response.raise_for_status()` | Catches 4xx/5xx errors uniformly instead of manual status check |
| `logging` instead of `print()` | Structured, configurable, redirectable — essential for Flask integration |
| `BASE_URL` constant | Eliminates magic string, single place to change |
| `DEFAULT_HEADERS` constant | Ready to share across modules (move to config later) |
| Type hints | Self-documenting, IDE support, catches bugs early |
| Docstring | Clarifies contract for other developers |
| `soup.find_all("a", href=True)` | Eliminates the `if not href: continue` check — cleaner |

---

## 3. File Review: `scrape_article.py`

### What's Good
- Uses JSON-LD extraction — very smart, more reliable than HTML scraping
- Normalizes whitespace in body text
- Returns `None` on failure — clean sentinel value
- Handles the `isinstance` check for data type

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | Bare `except Exception` swallows all errors silently | Exception Handling | **[MUST]** |
| 2 | No `requests.RequestException` handling — crash on network error | Exception Handling | **[MUST]** |
| 3 | No logging | Logging | **[MUST]** |
| 4 | Duplicate `headers` dict (also in `collect_links.py`) | DRY | **[SHOULD]** |
| 5 | `import json` unused if no LD+JSON found — minor but `json.JSONDecodeError` is swallowed | Readability | **[OPTIONAL]** |
| 6 | No type hints or docstring | Python Best Practices | **[SHOULD]** |
| 7 | Returns a raw `dict` — fragile, no schema guarantee | Maintainability | **[SHOULD]** |

### Improved Version

```python
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
        body = " ".join(body.split())  # normalize whitespace

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
        print(f"Title: {article['title']}")
        print(f"Published: {article['published_at']}")
        print(f"Body: {article['body'][:200]}...")
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| Catch `json.JSONDecodeError` specifically | You see *what* failed instead of silently swallowing errors |
| `script.string or ""` | Prevents `json.loads(None)` crash if script tag is empty |
| `response.raise_for_status()` | Uniform HTTP error handling |
| Logging at appropriate levels | `debug` for expected issues, `warning` for missing data, `error` for failures |
| Separated JSON parse from type check | Clearer flow, each `try` block has one responsibility |

---

## 4. File Review: `db.py`

### What's Good
- Uses parameterized queries (`%s`) — prevents SQL injection
- Has `finally: cursor.close()` — proper cleanup
- Catches `IntegrityError` for duplicates — graceful handling

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | **Hardcoded DB credentials** (`password="yuvi"`) at module level | **Security** | **[MUST]** 🔴 |
| 2 | **Global connection** created at import time — never closed, no reconnection | DB Connection Mgmt | **[MUST]** |
| 3 | If MySQL restarts, the global connection is dead and all inserts fail forever | Scalability | **[MUST]** |
| 4 | No logging — uses `print()` | Logging | **[MUST]** |
| 5 | `datetime.fromisoformat()` can crash on malformed dates — no handling | Exception Handling | **[SHOULD]** |
| 6 | Generic exceptions during `cursor.execute()` are not caught | Exception Handling | **[SHOULD]** |
| 7 | No docstring / type hints | Readability | **[SHOULD]** |
| 8 | Connection is committed per-row — inefficient for batch inserts | Performance | **[SHOULD]** |

> [!CAUTION]
> **`password="yuvi"` is hardcoded in source code.** This is the single most critical security issue in the project. If this repo is pushed to GitHub, the database password is public.

### Improved Version

```python
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
        database=os.getenv("DB_NAME", "maayboli_ai"),
        charset="utf8mb4",
    )


def insert_article(article: dict) -> bool:
    """Insert a single article into the database.

    Args:
        article: Dict with keys: title, body, url, published_at.

    Returns:
        True if inserted successfully, False otherwise.
    """
    query = """
        INSERT INTO articles (title, body, article_url, published_at)
        VALUES (%s, %s, %s, %s)
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
            cursor.execute(query, (
                article["title"],
                article["body"],
                article["url"],
                published_at,
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
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| `get_connection()` function | No stale global connection; each call gets a fresh connection; survives DB restarts |
| Credentials from env vars | Password is never in source code — safe for version control |
| `with connection.cursor()` | Context manager auto-closes cursor — no manual `finally` needed |
| `connection.close()` in `finally` | Connection is always released, prevents connection leaks |
| Return `bool` | Caller can track success/failure for batch reporting |
| Catch `ValueError` on date parse | Malformed dates no longer crash the entire pipeline |
| Catch generic `pymysql.Error` | Any unexpected DB error is logged, not a crash |

### Required `.env` additions

```env
GEMINI_API_KEY=your_key_here
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=yuvi
DB_NAME=maayboli_ai
```
