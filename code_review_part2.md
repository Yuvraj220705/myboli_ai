# Myboli AI — Code Review (Part 2 of 3)

## 5. File Review: `retriever.py`

### What's Good
- Clean FULLTEXT search query with `NATURAL LANGUAGE MODE`
- Uses `DictCursor` — returns dicts instead of tuples (clean)
- Parameterized query — no SQL injection
- `BODY_LIMIT` constant to truncate long bodies
- `ORDER BY score DESC` — correct relevance ranking

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | **Hardcoded DB credentials** (same as `db.py`) | **Security** | **[MUST]** 🔴 |
| 2 | **Separate global connection** — duplicates `db.py` connection, no sharing | DB Connection Mgmt | **[MUST]** |
| 3 | Global connection never closed, never reconnects | Resource Leak | **[MUST]** |
| 4 | `BODY_LIMIT = 1500` defined inside function + also in `gemini_service.py` | DRY | **[SHOULD]** |
| 5 | No exception handling — any DB error crashes the caller | Exception Handling | **[MUST]** |
| 6 | No logging | Logging | **[MUST]** |
| 7 | No docstring / type hints | Readability | **[SHOULD]** |
| 8 | Body truncation `[:BODY_LIMIT]` may cut mid-word | Readability | **[OPTIONAL]** |

> [!IMPORTANT]
> **Two separate global connections** (`db.py` and `retriever.py`) means two open MySQL connections at all times, even when idle. This also means if you fix credentials in one file, you must remember the other — a maintenance trap.

### Improved Version

```python
"""Retrieves articles from MySQL using FULLTEXT search."""

import logging
from typing import Optional

import pymysql

from db import get_connection

logger = logging.getLogger(__name__)

BODY_LIMIT = 1500


def search_articles(query: str, limit: int = 3) -> list[dict]:
    """Search articles using MySQL FULLTEXT search.

    Args:
        query: The search query string.
        limit: Maximum number of results to return.

    Returns:
        A list of article dicts with keys: title, body, article_url,
        published_at, score. Returns empty list on failure.
    """
    sql = """
        SELECT
            title,
            body,
            article_url,
            published_at,
            MATCH(title, body) AGAINST(%s IN NATURAL LANGUAGE MODE) AS score
        FROM articles
        WHERE MATCH(title, body) AGAINST(%s IN NATURAL LANGUAGE MODE)
        ORDER BY score DESC
        LIMIT %s
    """

    connection = get_connection()
    try:
        with connection.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(sql, (query, query, limit))
            articles = cursor.fetchall()

        for article in articles:
            body = article["body"] or ""
            truncated = " ".join(body.split())[:BODY_LIMIT]
            # Avoid cutting mid-word
            if len(truncated) < len(body) and " " in truncated:
                truncated = truncated[:truncated.rfind(" ")]
            article["body"] = truncated

        logger.info("Search '%s' returned %d results", query[:50], len(articles))
        return articles

    except pymysql.Error as e:
        logger.error("Search query failed: %s", e)
        return []
    finally:
        connection.close()
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| `from db import get_connection` | Single source of truth for DB connections — DRY, consistent credentials |
| `connection.close()` in `finally` | No connection leak; each search gets fresh connection |
| `with cursor` context manager | Auto-closes cursor |
| `pymysql.Error` catch | Search failure returns `[]` instead of crashing the API |
| `rfind(" ")` truncation | Body is truncated at word boundary, not mid-word |
| Cursor class passed at call site | `DictCursor` is explicit at usage, not baked into a global connection |
| Logging | Search queries and results are auditable |

---

## 6. File Review: `gemini_service.py`

### What's Good
- Uses `load_dotenv()` for API key
- Separates `build_context()` and `generate_answer()` — good decomposition
- Has a Marathi fallback message — thoughtful UX
- Prompt has grounding rules (don't hallucinate, use only context)

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | **Prompt is broken** — rules 1-4 and then rule "5." is empty, followed by a second set of instructions that partially repeat | **Prompt Engineering** | **[MUST]** 🔴 |
| 2 | `BODY_LIMIT = 1500` defined here AND in `retriever.py` — duplicate constant | DRY | **[SHOULD]** |
| 3 | No exception handling for Gemini API call — network/rate-limit errors crash | Exception Handling | **[MUST]** |
| 4 | `client` is global — fine for scripts, but blocks Flask's request-level error handling | Production Readiness | **[SHOULD]** |
| 5 | `model="gemini-3-flash-preview"` is hardcoded — should be configurable | Maintainability | **[SHOULD]** |
| 6 | No logging | Logging | **[MUST]** |
| 7 | No type hints / docstrings | Readability | **[SHOULD]** |
| 8 | `from retriever import search_articles` triggers DB connection at import time | Side Effects | **[SHOULD]** |
| 9 | No token/cost tracking | Production Readiness | **[OPTIONAL]** |

> [!WARNING]
> **The prompt is broken.** Look at lines 53-70 — rule 5 is empty, then the prompt restarts with a second set of instructions. This sends conflicting/redundant instructions to Gemini, wasting tokens and confusing the model.

### Current Broken Prompt (annotated)

```
Rules:
1. Answer ONLY using the articles below.
2. Do not make up information.
3. If the answer is not present, say: "..."
4. Answer in Marathi.
5.                                          ← EMPTY RULE
You are a news assistant.                   ← SECOND SYSTEM INSTRUCTION (redundant)
Use ONLY the information...                 ← REPEAT of rule 1
Do NOT use your own knowledge.              ← REPEAT of rule 2
If the answer is not completely present...  ← REPEAT of rule 3 (different Marathi text!)
Never add assumptions.                      ← NEW, but should be in the first list
```

### Improved Version

```python
"""Gemini AI service for answering questions using retrieved articles."""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai

from retriever import search_articles

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
NO_ANSWER_MSG = "माझ्याकडे या प्रश्नासंबंधी पुरेशी माहिती उपलब्ध नाही."

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_context(question: str) -> Optional[str]:
    """Build context string from retrieved articles.

    Args:
        question: The user's question for article retrieval.

    Returns:
        A formatted context string, or None if no articles found.
    """
    articles = search_articles(question)

    if not articles:
        return None

    parts = []
    for i, article in enumerate(articles, start=1):
        parts.append(
            f"Article {i}\n"
            f"Title: {article['title']}\n"
            f"Content: {article['body']}\n"
            f"{'—' * 40}"
        )

    return "\n\n".join(parts)


def generate_answer(question: str) -> str:
    """Generate an answer to a question using retrieved context and Gemini.

    Args:
        question: The user's question in Marathi or English.

    Returns:
        The generated answer string.
    """
    context = build_context(question)

    if context is None:
        logger.info("No context found for question: %s", question[:80])
        return NO_ANSWER_MSG

    prompt = f"""तुम्ही एक मराठी बातम्यांचे सहाय्यक (AI News Assistant) आहात.

नियम:
1. फक्त खालील लेखांमधील माहिती वापरा.
2. स्वतःचे ज्ञान वापरू नका.
3. माहिती नसल्यास सांगा: "{NO_ANSWER_MSG}"
4. उत्तर मराठीत द्या.
5. अंदाज लावू नका, गृहीतके धरू नका.

लेख:

{context}

प्रश्न: {question}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        logger.info("Gemini response generated for: %s", question[:80])
        return response.text
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return NO_ANSWER_MSG


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    q = input("Question: ")
    print("\n" + generate_answer(q))
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| **Fixed prompt** — single clean list of 5 rules | No duplicates, no empty rules, no conflicting fallback messages |
| Prompt in Marathi | Since the model answers in Marathi, Marathi instructions reduce language-switching confusion for the model |
| `NO_ANSWER_MSG` constant | Used in both the code fallback and the prompt — single source of truth |
| `GEMINI_MODEL` from env | Swap models without code change (e.g., `gemini-2.5-flash`) |
| `try/except` around API call | Rate limits, network errors, quota exhaustion won't crash the app |
| `"\n\n".join(parts)` | Cleaner string building than `+=` concatenation (avoids O(n²) string copies) |
| Logging | Track what questions are asked, when Gemini fails |

---

## 7. File Review: `main.py`

### What's Good
- Simple, linear pipeline — easy to understand
- Uses the module functions correctly

### Issues

| # | Issue | Category | Severity |
|---|---|---|---|
| 1 | **Duplicate imports** — `collect_links` and `scrape_article` imported twice | Dead Code | **[MUST]** |
| 2 | No `if __name__ == "__main__"` guard — runs on import | Python Best Practices | **[MUST]** |
| 3 | No exception handling — one bad article crashes the entire pipeline | Exception Handling | **[MUST]** |
| 4 | No logging | Logging | **[MUST]** |
| 5 | Hardcoded category URL | Maintainability | **[SHOULD]** |
| 6 | No progress reporting (how many succeeded/failed?) | Production Readiness | **[SHOULD]** |
| 7 | No rate limiting between requests — could get IP banned | Production Readiness | **[SHOULD]** |

### Improved Version

```python
"""Main pipeline: collect links → scrape articles → store in database."""

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
```

### Why Each Change Is Better

| Change | Why |
|---|---|
| Removed duplicate imports | Lines 1+4 and 2+5 were identical — dead code |
| `if __name__ == "__main__"` guard | Prevents pipeline from running when imported by Flask or tests |
| `time.sleep(1)` between requests | Polite scraping; avoids IP ban from Maharashtra Times |
| `stats` dict | Know exactly how many articles were scraped/inserted/failed |
| `try/except` per article | One bad article doesn't kill the entire batch |
| `run_pipeline()` function | Callable from Flask endpoint later, testable |
| `logging.basicConfig` with format | Timestamps + log levels in output |
