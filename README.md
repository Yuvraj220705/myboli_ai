# Maayboli AI — Marathi News RAG Chatbot

An end-to-end, intent-aware Retrieval-Augmented Generation (RAG) system for Marathi regional news queries. Designed with MySQL FULLTEXT retrieval, intent detection, and Google Gemini 1.5 Flash summarization.

---

## 📁 Project Structure

```text
myboli_ai/
├── app.py                            # Main REST API Server (Flask)
├── requirements.txt                  # Python dependencies
├── .env.example                      # Environment variables template
├── .gitignore                        # Standardized git ignore rules
├── README.md                         # Project documentation & setup guide
│
├── src/                              # Core RAG Application Logic Modules
│   ├── query_processor.py            # Intent & metadata extraction engine
│   ├── retriever.py                  # MySQL FULLTEXT retrieval engine
│   ├── gemini_service.py             # RAG prompt builder & Gemini client
│   ├── date_parser.py                # Devanagari date parsing utilities
│   └── db.py                         # MySQL connection pool manager
│
├── tests/                            # Automated test runners & benchmarks
│   ├── run_retrieval_benchmark.py    # 100-query retrieval benchmark runner
│   ├── generate_retrieval_report.py  # Query-by-query report generator
│   ├── benchmark.py                  # Fulltext performance evaluator
│   ├── test_api.py                   # REST API integration test loop
│   ├── test_search.py                # Retriever standalone search CLI test
│   ├── test_gemini.py                # Gemini service integration test
│   └── test_context.py               # RAG context builder test
│
├── evaluation/                       # Evaluation benchmarks & metrics outputs
│   ├── evaluation_queries/           # Test query datasets (.txt)
│   ├── retrieval_benchmark_results.csv # 100-query benchmark CSV metrics
│   ├── benchmark_results.json        # Retrieval benchmark JSON output
│   ├── benchmark_results.md          # Benchmark report summary
│   ├── scrape_report.json            # Ingestion metrics report
│   └── summary.json                  # Summary evaluation report
│
├── scripts/                          # News scraper & data ingestion tools
│   ├── main.py                       # Automated scraper & DB ingestion runner
│   ├── collect_links.py              # Web crawler link discovery module
│   ├── scrape_article.py             # JSON-LD & HTML article parser
│   └── failed_urls.txt               # Ingestion failure tracking log
│
├── docs/                             # Code reviews & detailed reports
│   ├── backend_code_review.md        # Code audit & architectural review
│   └── retrieval_benchmark_detailed_report.md # Query-by-query detailed report
│
└── logs/                             # Runtime log directory (gitignored)
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10+
- MySQL Server (with `myboli_ai` database configured with FULLTEXT indexes)

### 2. Environment Setup
Clone the repository and create a Python virtual environment:

```bash
git clone https://github.com/Yuvraj220705/myboli_ai.git
cd myboli_ai

# Create & activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🔑 Environment Variables

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

`.env` sample parameters:
```env
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_mysql_password
DB_NAME=myboli_ai
GEMINI_API_KEY=your_gemini_api_key
```

---

## 🚀 Running the Web Service

To start the Flask REST API server:

```bash
python app.py
```

The API will start at `http://localhost:5000`.

### REST Endpoints:
- `GET /health`: Health check endpoint.
- `POST /chatbot/ask`: Main chat interface endpoint.
  ```json
  {
    "question": "सिंधुदुर्ग मधील ताज्या घडामोडी काय आहेत?"
  }
  ```

---

## 🧪 Running Tests & Benchmarks

Execute retrieval and component tests directly:

### 1. Automated Retrieval Benchmark (100 Queries)
Runs evaluation against spelling variations without invoking Gemini:
```bash
python tests/run_retrieval_benchmark.py
```

### 2. Generate Detailed Retrieval Report
Generates a full Markdown query-by-query analysis in `docs/retrieval_benchmark_detailed_report.md`:
```bash
python tests/generate_retrieval_report.py
```

### 3. Direct Search & API Tests
```bash
# Test direct FULLTEXT search from CLI
python tests/test_search.py

# Test Flask REST API endpoint
python tests/test_api.py
```

---

## 📥 Running the Ingestion Scraper

To run the automated news article crawler & database ingestion pipeline:

```bash
python scripts/main.py
```

Ingestion execution logs and reports will save automatically into `evaluation/scrape_report.json`.
