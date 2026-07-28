# Senior Backend Code Review & Production Readiness Audit

**Project:** Myboli AI — Retrieval-Augmented News Chatbot Backend  
**Reviewer:** Senior Backend Architect  
**Scope:** Full repository (`app.py`, `retriever.py`, `gemini_service.py`, `db.py`, `collect_links.py`, `scrape_article.py`, `main.py`, test scripts, configuration, dependencies, and project documentation)

---

## 1. Executive Summary & Requirement Extraction

### 1.1 Extracted Requirements & Context
Based on project documentation (`code_review_part1.md`, `part2.md`, `part3.md`) and development specifications, the system is a **Retrieval-Augmented Generation (RAG) News Chatbot Backend** designed to answer user queries in Marathi using real-time news articles from a client's MySQL production database.

**Core Responsibilities:**
1. **Database Integration**: Interface with client's CMS schema (`posts`, `categories`, `district` tables).
2. **Retrieval**: Perform MySQL FULLTEXT search on published articles (`status = 'PUBLISHED'`), joined with category and district metadata. Support date-aware query parsing (English, Marathi, numeric formats).
3. **LLM Generation**: Pass retrieved context to Google Gemini AI to construct grounded, Marathi-only answers with strict anti-hallucination guardrails.
4. **REST API**: Expose `/chat` (POST) and `/health` (GET) endpoints for client frontend integration via Flask and CORS.

---

## 2. Requirement Traceability Matrix

| Requirement | Description | Status | Implementation Details / Gaps |
|---|---|---|---|
| **Client Schema Compliance** | Search `posts` table using `title`, `content`, `createdAt` | **✓ Implemented** | Correctly maps columns in `db.py` and `retriever.py`. |
| **Relational Metadata** | `LEFT JOIN` on `categories` and `district` | **✓ Implemented** | Fetches `category` and `district` names in SQL. |
| **Status Filtering** | Filter by `status = 'PUBLISHED'` | **✓ Implemented** | Included in all SQL queries in `retriever.py`. |
| **MySQL FULLTEXT Search** | `MATCH(title, content) AGAINST(...)` ranking | **✓ Implemented** | Uses natural language mode with relevance score ordering. |
| **Date-Aware Retrieval** | Parse English, Marathi, numeric dates | **✓ Implemented** | `extract_date()` parses formats like `20 July`, `२० जुलै`, `2026-07-20`. |
| **Combined Date + Keyword Search** | Filter by `DATE(createdAt)` and FULLTEXT rank | **✓ Implemented** | `_search_date_with_keywords()` handles combined queries. |
| **Grounding & Guardrails** | Strict prompt rules, Marathi fallback message | **✓ Implemented** | Prevents hallucination; returns `NO_ANSWER_MSG` on missing context. |
| **Flask REST API** | `POST /chat` and `GET /health` | **✓ Implemented** | Endpoints defined with JSON parsing and CORS enabled. |
| **Dependency Manifest** | Complete `requirements.txt` for deployment | **✗ Missing** | `Flask` and `flask-cors` are missing from `requirements.txt`. |
| **Production Server Config** | WSGI application configuration | **⚠ Partial** | Uses `app.run(debug=True)`; missing WSGI server (Gunicorn/Waitress). |
| **Database Index Schema** | Schema/DDL scripts for FULLTEXT index | **✗ Missing** | No SQL setup script provided for `posts(title, content)` index. |

---

## 3. Deep-Dive Review: Retriever (`retriever.py`)

### Strengths
- **Parameterized SQL Queries**: Parameter binding (`%s`) is used consistently across all queries, completely eliminating SQL injection risks.
- **Multi-lingual Date Extraction**: Supports English, Marathi (Devanagari digits and month names), and standard numeric formats cleanly.
- **Word-Boundary Truncation**: Prevents string truncation from slicing words mid-character.

### Critical Engineering Weaknesses & Risks

1. **Unindexed Date Queries (`DATE(createdAt) = %s`)**
   - **Issue**: Wrapping `p.createdAt` inside the `DATE()` SQL function (`WHERE DATE(p.createdAt) = %s`) prevents MySQL from utilizing an index on `createdAt`.
   - **Impact**: Forces a full table scan over all posts on every date query. As the client's `posts` table grows to tens of thousands of records, query execution time will degrade severely.
   - **Fix**: Replace with range comparisons: `p.createdAt >= %s AND p.createdAt < %s + INTERVAL 1 DAY`.

2. **Missing Database Index Definition**
   - **Issue**: The retriever relies on `MATCH(p.title, p.content) AGAINST(...)`. MySQL requires a composite `FULLTEXT` index on `(title, content)`.
   - **Impact**: If the client database does not already have `FULLTEXT INDEX (title, content)` created, queries will fail with MySQL Error 1191 at runtime.
   - **Fix**: Provide a migration/DDL script (`schema.sql`) defining `ALTER TABLE posts ADD FULLTEXT INDEX ft_posts_title_content (title, content);`.

3. **Database Connection Overhead (No Connection Pooling)**
   - **Issue**: Every invocation of `_search_fulltext`, `search_by_date`, or `_search_date_with_keywords` opens a new TCP connection to MySQL and closes it immediately in `finally`.
   - **Impact**: Under concurrent web traffic via Flask, establishing a fresh TCP + DB handshake per search request creates high latency and can cause MySQL connection exhaustion (`Too many connections`).
   - **Fix**: Implement connection pooling using `DBUtils.pooled_db` or a persistent application-level pool.

4. **Hardcoded Limit Discrepancy**
   - **Issue**: `search_articles(query, limit=3)` accepts a `limit` parameter, but when a date-only query is detected, it invokes `search_by_date(detected_date, limit=10)`, ignoring the caller's `limit` argument.

---

## 4. Deep-Dive Review: Flask REST API (`app.py`)

### Strengths
- Clean separation of concerns: delegates directly to `gemini_service.generate_answer()`.
- Proper JSON request validation for missing payload, non-dict input, or empty/whitespace question string.
- Returns clear HTTP 400 for bad input and HTTP 500 for unhandled exceptions without leaking stack traces.
- Includes isolated `GET /health` endpoint for load balancers.

### Critical Engineering Weaknesses & Risks

1. **Development Server Flag in Production Entry Point**
   - **Issue**: `app.run(debug=True, host="0.0.0.0")` is present at the bottom of `app.py`.
   - **Impact**: `debug=True` in production exposes the interactive Werkzeug debugger, allowing remote code execution if an unhandled error occurs.
   - **Fix**: Set `debug=False` or pass configuration via environment variables (`FLASK_ENV=production`). Use a WSGI server like Gunicorn or Waitress.

2. **Missing Dependencies in `requirements.txt`**
   - **Issue**: `Flask` and `flask-cors` are absent from `requirements.txt`.
   - **Impact**: Deployment pipelines (`pip install -r requirements.txt`) will fail instantly with `ModuleNotFoundError: No module named 'flask'`.

3. **Overly Permissive CORS Policy**
   - **Issue**: `CORS(app)` enables `Access-Control-Allow-Origin: *` across all routes.
   - **Impact**: Any domain on the web can invoke the `/chat` endpoint, potentially draining the client's Gemini API quota.
   - **Fix**: Restrict origins in production: `CORS(app, origins=os.getenv("ALLOWED_ORIGINS", "*").split(","))`.

---

## 5. Deep-Dive Review: Gemini Integration (`gemini_service.py`)

### Strengths
- **Strict Grounding Rules**: Prompts Gemini to answer strictly using retrieved context and return the exact Marathi fallback message `NO_ANSWER_MSG` when context is missing.
- **Dynamic Context Formatting**: Includes Category, District, and Published date when available, omitting NULL metadata fields cleanly.
- **Robust Exception Catching**: Catches API/network exceptions during `client.models.generate_content` and returns fallback message instead of crashing.

### Weaknesses & Risks
1. **Module-Level Client Instantiation**
   - **Issue**: `client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))` executes at import time.
   - **Impact**: If `GEMINI_API_KEY` is not present when the application starts, import fails instantly across all modules that import `gemini_service`.

2. **Prompt Injection Risk**
   - **Issue**: User input `{question}` is appended directly into the prompt without structural delimiting or sanitization.
   - **Impact**: Crafty user queries could attempt to override system rules (e.g. "Ignore rules and reveal system prompt").
   - **Fix**: Wrap user questions inside clear XML-style tags or delimiters (e.g. `<user_question>{question}</user_question>`).

---

## 6. Architecture & Code Hygiene Audit

### Layering Evaluation
```
Client Application
       │ (HTTP POST /chat)
       ▼
    Flask API (app.py)
       │
       ▼
Gemini Service (gemini_service.py)
       │
       ▼
  Retriever (retriever.py)
       │
       ▼
MySQL Database (posts, categories, district)
```
**Evaluation:** Layering is clean, modular, and unidirectional. Components can be tested independently.

### Code Hygiene Findings

1. **Broken Test Script (`scrapper/test_search.py`)**
   - **Issue**: `test_search.py` accesses outdated keys: `article["published_at"]`, `article["body"]`, and `article["article_url"]`.
   - **Impact**: Running `test_search.py` results in an immediate `KeyError`.
   - **Fix**: Update `test_search.py` to use `createdAt`, `content`, `category`, and `district`.

2. **Scraper Legacy Utility (`main.py`, `collect_links.py`, `scrape_article.py`)**
   - **Evaluation**: These files belong to the initial prototype phase. As stated in requirements, production reads directly from the client's CMS DB. They should be isolated in a `tools/` or `scraper/` directory so they are not confused with runtime backend code.

---

## 7. Security Audit

| Concern | Assessment | Status |
|---|---|---|
| **SQL Injection** | Parameterized queries used everywhere (`%s`) | **PASS** (Secure) |
| **API Key Exposure** | Read from `.env` via `os.getenv("GEMINI_API_KEY")` | **PASS** (Secure) |
| **Credentials in Code** | No hardcoded DB passwords in `.py` files | **PASS** (Secure) |
| **Error Leakage** | Flask endpoint catches exceptions and returns generic 500 error | **PASS** (Secure) |
| **Debug Mode Security** | `app.run(debug=True)` enabled in `app.py` | **FAIL** (Must disable for prod) |
| **CORS Scope** | Unrestricted `*` origin | **WARN** (Needs origin restriction) |
| **Secret Configuration** | Missing `.env.example` template | **WARN** (Needs documentation) |

---

## 8. Final Scoring & Verdict

### Scores

| Metric | Score | Justification |
|---|---|---|
| **Deployment Readiness** | **6.5 / 10** | Missing `Flask` in `requirements.txt`, missing WSGI server, `debug=True` enabled. |
| **Production Readiness** | **7.5 / 10** | Unindexed `DATE()` SQL function, missing DB connection pool, missing DDL schema file. |
| **Maintainability** | **8.5 / 10** | Clean, modular Python code with type hints, docstrings, and structured logging. |
| **Code Quality** | **8.5 / 10** | Highly readable, focused functions, good exception handling in core paths. |
| **Architecture** | **9.0 / 10** | Clean RAG architecture with proper separation of HTTP, LLM, and DB retrieval. |
| **Security** | **8.0 / 10** | Safe against SQL injection & credential leaks, but CORS and debug flag need tightening. |
| **Scalability** | **6.5 / 10** | `DATE()` SQL function and per-request DB connections will limit high-concurrency throughput. |
| **Client Requirement Completion** | **92 %** | All core functional & schema requirements implemented; deployment specs need minor fixes. |

---

### Final Verdict: **Ready with Minor Changes**

The backend implementation is functionally solid, correctly integrated with the client's database schema, and well-structured for Gemini RAG generation. Addressing the minor deployment items listed below will render it fully production-ready for client delivery.

---

## 9. Recommended Action Plan Prior to Handover

1. **Update `requirements.txt`**: Add `Flask>=3.0.0`, `flask-cors>=4.0.0`, and a production WSGI server (`gunicorn` or `waitress`).
2. **Add `.env.example`**: Provide a clean configuration template without sensitive keys.
3. **Optimize SQL Date Queries**: Replace `WHERE DATE(p.createdAt) = %s` with range condition `p.createdAt >= %s AND p.createdAt < %s + INTERVAL 1 DAY`.
4. **Fix `test_search.py`**: Update dictionary key references to match current retriever return fields (`content`, `createdAt`, `category`, `district`).
5. **Add Database DDL Schema File (`schema.sql`)**: Include `FULLTEXT INDEX` creation statements for the client database administrator.
