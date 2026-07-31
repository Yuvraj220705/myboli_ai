# Myboli AI — Code Review (Part 3 of 3)

## 8. Test Files Review

### Current State

| File | Purpose | Issue |
|---|---|---|
| `test.py` | Test Gemini connectivity | Runs at module level, no assertions, hardcoded |
| `test_context.py` | Test context building | Uses `input()`, not automatable |
| `test_gemini.py` | Test full Q&A pipeline | Uses `input()`, not automatable |
| `test_search.py` | Test FULLTEXT search | Uses `input()`, not automatable |
| `list_models.py` | List available Gemini models | Dev utility, not a test |

### Issues

| # | Issue | Severity |
|---|---|---|
| 1 | None of these are real tests — no assertions, no test framework | **[SHOULD]** |
| 2 | All use `input()` — cannot be automated | **[SHOULD]** |
| 3 | Mixed in with production code | **[SHOULD]** |
| 4 | `test.py` name conflicts with Python's `test` stdlib module | **[SHOULD]** |

### Recommendation

Keep these as manual dev scripts but move them to a `tests/` folder and rename `test.py` to `test_gemini_connection.py`. For client delivery, this is acceptable — real unit tests are a **[OPTIONAL]** enhancement.

---

## 9. Cross-Cutting Concerns

### 9.1 Duplicate Code Across Files

| Duplication | Files | Fix |
|---|---|---|
| `headers = {"User-Agent": "Mozilla/5.0"}` | `collect_links.py`, `scrape_article.py` | Define once, import |
| DB credentials (host, user, pass, db) | `db.py`, `retriever.py` | Single `get_connection()` in `db.py` |
| `BODY_LIMIT = 1500` | `retriever.py`, `gemini_service.py` | Define once in `retriever.py` |
| `load_dotenv()` + `genai.Client()` init | `gemini_service.py`, `test.py`, `list_models.py` | Acceptable (test files are standalone) |

### 9.2 Environment Variable Usage

**Current:** Only `GEMINI_API_KEY` is in `.env`. Everything else is hardcoded.

**Required `.env` for production:**

```env
# API Keys
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-3-flash-preview

# Database
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password_here
DB_NAME=maayboli_ai
```

**Severity: [MUST]** — credentials must never be in source code.

### 9.3 Logging Strategy

**Current:** All files use `print()`. This is unsuitable for production because:
- No timestamps
- No log levels (can't filter errors from info)
- Can't redirect to file
- Flask will suppress `print()` output

**Recommended:** Add a `logging_config.py` or configure in the app entry point:

```python
# Add to the top of main.py or your Flask app.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

Then every module uses:
```python
import logging
logger = logging.getLogger(__name__)
logger.info("message")
```

**Severity: [MUST]**

### 9.4 Database Connection Management

**Current (2 separate global connections):**
```
db.py        → pymysql.connect(...)     ← connection #1 (never closed)
retriever.py → pymysql.connect(...)     ← connection #2 (never closed)
```

**Problems:**
1. Two open connections, even when idle
2. If MySQL restarts, both connections are dead forever
3. Credentials duplicated
4. No connection pooling

**Recommended (single `get_connection()` function):**
```
db.py        → get_connection()  ← creates fresh connection
retriever.py → from db import get_connection  ← reuses same factory
```

For a Flask API later, consider connection pooling with `DBUtils` or `pymysql`'s built-in pool — but that's **[OPTIONAL]** for now.

**Severity: [MUST]**

### 9.5 Request Session Management

**Current:** Each call to `requests.get()` creates a new TCP connection.

**For the current scale** (scraping one category page), this is **fine**. If you later scrape thousands of pages, use `requests.Session()` for connection reuse:

```python
session = requests.Session()
session.headers.update(DEFAULT_HEADERS)
# reuse `session.get(url)` in a loop
```

**Severity: [OPTIONAL]** — current scale doesn't need it.

### 9.6 `.gitignore` (Missing)

```gitignore
# Python
__pycache__/
*.pyc
*.pyo

# Virtual environment
.venv/

# Environment variables
.env

# IDE
.vscode/
.idea/
```

**Severity: [MUST]**

### 9.7 `requirements.txt` Consolidation

**Current:** Two requirements files, root one doesn't include `google-genai`.

**Recommended single `requirements.txt`:**

```
beautifulsoup4>=4.15.0
google-genai>=1.0.0
PyMySQL>=1.2.0
python-dotenv>=1.2.0
requests>=2.34.0
```

Remove `scrapper/requirements.txt`. Keep only the root one.

**Severity: [MUST]**

---

## 10. Master Issue Tracker

### 🔴 [MUST] — Required Before Client Delivery

| # | Issue | File(s) | Category |
|---|---|---|---|
| 1 | Hardcoded DB password in source code | `db.py`, `retriever.py` | Security |
| 2 | Two separate global DB connections, never closed | `db.py`, `retriever.py` | DB Connection Mgmt |
| 3 | No exception handling on `requests.get()` | `collect_links.py`, `scrape_article.py` | Exception Handling |
| 4 | No exception handling on Gemini API call | `gemini_service.py` | Exception Handling |
| 5 | No exception handling on DB operations in retriever | `retriever.py` | Exception Handling |
| 6 | Broken/duplicate prompt (empty rule 5, repeated instructions) | `gemini_service.py` | Prompt Engineering |
| 7 | Duplicate imports | `main.py` | Dead Code |
| 8 | No `__main__` guard — pipeline runs on import | `main.py` | Python Best Practices |
| 9 | `print()` everywhere instead of `logging` | All files | Logging |
| 10 | Missing `.gitignore` | Project root | Security |
| 11 | Two conflicting `requirements.txt` files | Project root + scrapper/ | Maintainability |
| 12 | Bare `except Exception` swallows errors silently | `scrape_article.py` | Exception Handling |

### 🟡 [SHOULD] — Recommended Improvements

| # | Issue | File(s) | Category |
|---|---|---|---|
| 13 | No type hints on any function | All files | Python Best Practices |
| 14 | No docstrings on any function | All files | Readability |
| 15 | Magic strings (domain URL, user-agent) duplicated | `collect_links.py`, `scrape_article.py` | DRY |
| 16 | `BODY_LIMIT` constant duplicated | `retriever.py`, `gemini_service.py` | DRY |
| 17 | Gemini model name hardcoded | `gemini_service.py` | Maintainability |
| 18 | No rate limiting between scrape requests | `main.py` | Production Readiness |
| 19 | No progress/stats reporting in pipeline | `main.py` | Production Readiness |
| 20 | `scrapper/` folder name typo | Project structure | Readability |
| 21 | Date parsing can crash on malformed input | `db.py` | Exception Handling |
| 22 | Test files mixed with production code | Project structure | Maintainability |
| 23 | Missing `__init__.py` for package | `scrapper/` | Flask Readiness |

### 🟢 [OPTIONAL] — Nice to Have

| # | Issue | File(s) | Category |
|---|---|---|---|
| 24 | Use `requests.Session()` for connection reuse | Scraper files | Performance |
| 25 | Body truncation cuts mid-word | `retriever.py` | Readability |
| 26 | Real test framework (pytest) | Test files | Maintainability |
| 27 | Connection pooling for Flask | `db.py` | Scalability |

---

## 11. Flask API Readiness Assessment

When you add Flask, you'll need these things to be in place:

| Requirement | Current State | Action |
|---|---|---|
| Functions (not scripts) | `main.py` runs at module level | Wrap in `run_pipeline()` |
| `__main__` guards | Missing | Add to all files |
| Error handling | Missing everywhere | Add try/except |
| Logging | Uses `print()` | Switch to `logging` |
| DB connections | Global, stale | Use `get_connection()` per request |
| Config from env | Partial (only API key) | Move all config to `.env` |
| CORS | N/A yet | Add `flask-cors` when needed |
| Input validation | N/A yet | Validate query params |

### Minimal Flask App Structure (when ready)

```python
"""Flask API for Myboli AI news assistant."""

from flask import Flask, request, jsonify
from gemini_service import generate_answer

app = Flask(__name__)


@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json()
    question = data.get("question", "").strip()

    if not question:
        return jsonify({"error": "Question is required"}), 400

    answer = generate_answer(question)
    return jsonify({"question": question, "answer": answer})


if __name__ == "__main__":
    app.run(debug=True)
```

This will work cleanly **only after** the [MUST] issues above are fixed.

---

## 12. Priority Action Plan

### Phase 1 — Security & Stability (do first)
1. Move all credentials to `.env`
2. Create `.gitignore`
3. Consolidate to single `requirements.txt`
4. Create `get_connection()` in `db.py`, use it in `retriever.py`

### Phase 2 — Robustness
5. Add `try/except` to all `requests.get()` calls
6. Add `try/except` to Gemini API call
7. Add `try/except` to DB operations in `retriever.py`
8. Fix the broken prompt in `gemini_service.py`
9. Fix duplicate imports in `main.py`

### Phase 3 — Production Quality
10. Replace all `print()` with `logging`
11. Add `if __name__ == "__main__"` guards
12. Add type hints and docstrings
13. Extract constants (headers, URLs, body limit)
14. Add `time.sleep()` between scrape requests
15. Add `__init__.py` to the package

### Phase 4 — Flask Integration
16. Add Flask app with `/api/ask` endpoint
17. Add input validation
18. Add CORS if needed

---

> [!TIP]
> **The codebase is fundamentally sound.** The architecture is clean, the FULLTEXT search approach is pragmatic, and the JSON-LD extraction is clever. The issues are mostly about hardening — error handling, credentials management, and logging. Fixing the 12 [MUST] issues will make this production-ready.
