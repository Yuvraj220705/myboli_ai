"""Benchmarking tool for the Myboli AI Marathi News Retrieval System.

Reads all .txt query files from the evaluation directory, evaluates the retrieval
pipeline for each query, and produces structured JSON and Markdown reports.

Usage:
    python benchmark.py
    python benchmark.py --queries-dir evaluation_queries --top-k 5
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Force UTF-8 output on Windows terminals
import sys as _sys
if _sys.stdout.encoding and _sys.stdout.encoding.lower() != 'utf-8':
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from date_parser import _MARATHI_MONTHS, _ENGLISH_MONTHS, extract_date
from query_processor import DISTRICTS, CATEGORY_ALIASES, process_query
from retriever import search_articles

# --- Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ----------------------------
# Constants
# ----------------------------

QUERIES_DIR_DEFAULT = "evaluation_queries"
TOP_K_DEFAULT = 5
OUTPUT_JSON = "benchmark_results.json"
OUTPUT_MD = "benchmark_results.md"
OUTPUT_SUMMARY = "summary.json"

# Known person names for basic entity classification
_KNOWN_PERSONS = {
    "विनायक राऊत", "उदय सामंत", "एकनाथ शिंदे", "देवेंद्र फडणवीस",
    "अजित पवार", "सचिन अहिर", "उद्धव ठाकरे", "वैभव नाईक",
    "गिरीजा राऊत", "संजू परब", "रमेश सोलंकी",
}

# Known event / incident keywords
_EVENT_KEYWORDS = {
    "अपघात", "दुर्घटना", "चोरी", "अटक", "मृत्यू", "आग", "पूर",
    "आंदोलन", "मोर्चा", "तक्रार", "बलात्कार", "हल्ला", "स्फोट",
}

# Common Marathi stopwords
_STOPWORDS = {
    "काय", "आहे", "का", "आणि", "ते", "या", "ला", "ने", "चा", "ची",
    "च्या", "मध्ये", "मधील", "तील", "बद्दल", "सांगा", "माहिती",
    "बातमी", "बातम्या", "अपडेट", "सर्व", "वृत्त", "एक", "दोन",
    "घडलं", "घडले", "झालं", "झाले", "होतं", "होते", "आज", "काल",
    "on", "of", "in", "the", "what", "happened", "news", "updates",
}

# Marathi date filler words
_DATE_WORDS = {
    "आजच्या", "कालच्या", "आज", "काल", "आठवड्यातील", "महिन्यातील",
    "रोजी", "तारखेला", "जानेवारी", "फेब्रुवारी", "मार्च", "एप्रिल",
    "मे", "जून", "जुलै", "ऑगस्ट", "सप्टेंबर", "ऑक्टोबर", "नोव्हेंबर",
    "डिसेंबर",
}
_DATE_WORDS.update(_MARATHI_MONTHS.keys())
_DATE_WORDS.update(_ENGLISH_MONTHS.keys())


# ----------------------------
# Query File Parsing
# ----------------------------

def load_query_files(queries_dir: str) -> Dict[str, List[str]]:
    """Load all .txt benchmark query files from the given directory.

    Skips comment lines (starting with #) and empty lines.

    Args:
        queries_dir: Path to the directory containing .txt benchmark files.

    Returns:
        Dict mapping filename (without .txt) to list of query strings.
    """
    query_dir = Path(queries_dir)
    if not query_dir.exists():
        logger.error("Benchmark queries directory not found: %s", queries_dir)
        return {}

    file_map: Dict[str, List[str]] = {}
    txt_files = sorted(query_dir.glob("*.txt"))

    if not txt_files:
        logger.warning("No .txt files found in %s", queries_dir)
        return {}

    for txt_file in txt_files:
        queries = []
        try:
            for line in txt_file.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    queries.append(stripped)
            file_map[txt_file.stem] = queries
            logger.info("Loaded %d queries from %s", len(queries), txt_file.name)
        except IOError as e:
            logger.error("Failed to read %s: %s", txt_file, e)

    return file_map


# ----------------------------
# Keyword Classification
# ----------------------------

def _classify_token(token: str) -> Tuple[str, str]:
    """Classify a single query token into a keyword type.

    Returns:
        Tuple of (keyword_type, reason).
    """
    token_lower = token.lower().strip()

    # Numeric / Devanagari digit → likely a date day/year
    if re.match(r"^[\d०-९]+$", token):
        return "date", "Numeric token — likely day or year"

    # Punctuation only
    if re.match(r"^[^\w\s]+$", token):
        return "noise", "Punctuation or symbol only"

    # Stopword
    if token in _STOPWORDS or token_lower in _STOPWORDS:
        return "stopword", "Common Marathi filler or question word"

    # Date word
    if token in _DATE_WORDS or token_lower in _DATE_WORDS:
        return "date", "Marathi or English month/time keyword"

    # District
    for marathi_name in DISTRICTS:
        if re.search(re.escape(marathi_name), token):
            return "district", f"Matches district: {marathi_name}"

    # Category
    for canonical, aliases in CATEGORY_ALIASES.items():
        for alias in aliases:
            if re.search(re.escape(alias), token):
                return "category", f"Matches category: {canonical}"

    # Known person
    for person in _KNOWN_PERSONS:
        if re.search(re.escape(person.split()[0]), token):
            return "person", f"Matches known person: {person}"

    # Known event
    if token in _EVENT_KEYWORDS or token_lower in _EVENT_KEYWORDS:
        return "event", "Known event or incident keyword"

    # Single short token that won't help FULLTEXT
    if len(token) <= 2:
        return "ignored", "Token too short for FULLTEXT matching"

    return "general", "General content keyword"


def analyze_keywords(query: str, clean_query: str) -> List[Dict[str, Any]]:
    """Classify every whitespace-separated token in the query.

    Args:
        query: The original user query.
        clean_query: The cleaned query after processing.

    Returns:
        List of dicts with keyword analysis for each token.
    """
    tokens = query.split()
    clean_tokens = set(clean_query.split())
    results = []

    for token in tokens:
        kw_type, reason = _classify_token(token)
        was_removed = token not in clean_tokens
        was_searched = token in clean_tokens and kw_type not in ("stopword", "noise", "ignored")

        results.append({
            "keyword": token,
            "type": kw_type,
            "was_removed": was_removed,
            "was_searched": was_searched,
            "did_affect_retrieval": was_searched,
            "reason": reason,
        })

    return results


# ----------------------------
# Article Serialization
# ----------------------------

def serialize_article(rank: int, article: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a retrieved article dict into a benchmark-safe serializable record.

    Args:
        rank: 1-based rank position in the result list.
        article: Article dict from search_articles().

    Returns:
        Dict with all serializable article fields.
    """
    created_at = article.get("createdAt")
    published_str = created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at or "")

    content = article.get("content") or ""
    preview = content[:200].strip()

    return {
        "rank": rank,
        "score": round(float(article.get("score") or 0.0), 6),
        "article_id": article.get("id"),
        "title": article.get("title", ""),
        "district": article.get("district", ""),
        "category": article.get("category", ""),
        "published_date": published_str,
        "content_preview": preview,
    }


# ----------------------------
# Core Benchmark Runner
# ----------------------------

def evaluate_query(
    query: str,
    benchmark_file: str,
    section_name: str,
    top_k: int,
) -> Dict[str, Any]:
    """Evaluate a single query through the full retrieval pipeline.

    Args:
        query: The raw user query string.
        benchmark_file: Name of the source benchmark file.
        section_name: Section name from the benchmark file.
        top_k: Maximum number of results to retrieve.

    Returns:
        Complete evaluation record dict for this query.
    """
    timestamp = datetime.now().isoformat()

    # --- Process query (intent extraction) ---
    try:
        query_info = process_query(query)
    except Exception as e:
        logger.error("query_processor failed for '%s': %s", query[:50], e)
        query_info = None

    processed_query = query_info.clean_query if query_info else ""
    detected_district = query_info.district if query_info else None
    detected_category = query_info.category if query_info else None
    detected_date = str(query_info.date) if (query_info and query_info.date) else None

    # --- Keyword analysis ---
    keyword_analysis = analyze_keywords(query, processed_query)

    # Detect person tokens
    person_tokens = [k["keyword"] for k in keyword_analysis if k["type"] == "person"]
    event_tokens = [k["keyword"] for k in keyword_analysis if k["type"] == "event"]

    # --- Retrieval ---
    start_time = time.perf_counter()
    articles: List[Dict[str, Any]] = []
    error_message: Optional[str] = None

    try:
        articles = search_articles(query, top_k=top_k)
    except Exception as e:
        error_message = str(e)
        logger.error("search_articles failed for '%s': %s", query[:50], e)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

    # --- Serialize results ---
    serialized_articles = [serialize_article(i + 1, art) for i, art in enumerate(articles)]

    return {
        "timestamp": timestamp,
        "benchmark_file": benchmark_file,
        "section_name": section_name,
        "query": query,
        "processed_query": processed_query,
        "detected_district": detected_district,
        "detected_category": detected_category,
        "detected_date": detected_date,
        "detected_persons": person_tokens,
        "detected_events": event_tokens,
        "final_search_string": processed_query or query,
        "top_k_requested": top_k,
        "execution_ms": elapsed_ms,
        "num_results": len(articles),
        "error": error_message,
        "keywords": keyword_analysis,
        "results": serialized_articles,
    }


# ----------------------------
# Report Generators
# ----------------------------

def write_json_report(records: List[Dict[str, Any]], output_path: str) -> None:
    """Write full raw evaluation data to a JSON file."""
    try:
        Path(output_path).write_text(
            json.dumps(records, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved benchmark_results.json → %s", output_path)
    except IOError as e:
        logger.error("Failed to write JSON report: %s", e)


def write_markdown_report(records: List[Dict[str, Any]], output_path: str) -> None:
    """Write a human-readable Markdown report for each evaluated query."""
    lines = ["# Myboli AI — Retrieval Benchmark Report\n"]
    lines.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    lines.append(f"**Total Queries Evaluated:** {len(records)}\n")
    lines.append("---\n")

    current_file = None

    for rec in records:
        # Section header per benchmark file
        if rec["benchmark_file"] != current_file:
            current_file = rec["benchmark_file"]
            lines.append(f"\n## [{current_file}\n")

        lines.append("=" * 60)
        lines.append(f"\n**Query:** `{rec['query']}`\n")
        lines.append(f"- **Processed Query:** `{rec['processed_query'] or '—'}`")
        lines.append(f"- **District Detected:** `{rec['detected_district'] or 'None'}`")
        lines.append(f"- **Category Detected:** `{rec['detected_category'] or 'None'}`")
        lines.append(f"- **Date Detected:** `{rec['detected_date'] or 'None'}`")
        lines.append(f"- **Persons Detected:** `{', '.join(rec['detected_persons']) or 'None'}`")
        lines.append(f"- **Events Detected:** `{', '.join(rec['detected_events']) or 'None'}`")
        lines.append(f"- **Execution Time:** `{rec['execution_ms']} ms`")
        lines.append(f"- **Results Retrieved:** `{rec['num_results']}`")

        if rec.get("error"):
            lines.append(f"- ERROR: `{rec['error']}`")

        if rec["results"]:
            lines.append("\n| Rank | Score | Title | District | Category | Published |")
            lines.append("|------|-------|-------|----------|----------|-----------|")
            for art in rec["results"]:
                title = (art["title"] or "")[:60]
                lines.append(
                    f"| {art['rank']} | {art['score']:.4f} | {title} "
                    f"| {art['district'] or '—'} | {art['category'] or '—'} "
                    f"| {art['published_date'][:10] if art['published_date'] else '—'} |"
                )
        else:
            lines.append("\n> No articles retrieved.")

        lines.append("\n")

    try:
        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        logger.info("Saved benchmark_results.md → %s", output_path)
    except IOError as e:
        logger.error("Failed to write Markdown report: %s", e)


def write_summary_report(records: List[Dict[str, Any]], output_path: str) -> None:
    """Write aggregated summary statistics to summary.json."""
    exec_times = [r["execution_ms"] for r in records]
    result_counts = [r["num_results"] for r in records]
    successful = [r for r in records if r["error"] is None]
    failed = [r for r in records if r["error"] is not None]
    zero_results = [r for r in records if r["num_results"] == 0]

    # Per-file breakdown
    files_seen: Dict[str, Dict[str, Any]] = {}
    for r in records:
        f = r["benchmark_file"]
        if f not in files_seen:
            files_seen[f] = {"total": 0, "zero_results": 0, "avg_results": 0, "results_sum": 0}
        files_seen[f]["total"] += 1
        files_seen[f]["results_sum"] += r["num_results"]
        if r["num_results"] == 0:
            files_seen[f]["zero_results"] += 1
    for f in files_seen:
        total = files_seen[f]["total"]
        files_seen[f]["avg_results"] = round(files_seen[f]["results_sum"] / total, 2) if total else 0
        del files_seen[f]["results_sum"]

    summary = {
        "generated_at": datetime.now().isoformat(),
        "total_queries": len(records),
        "successful_queries": len(successful),
        "failed_queries": len(failed),
        "zero_result_queries": len(zero_results),
        "avg_execution_ms": round(sum(exec_times) / len(exec_times), 2) if exec_times else 0,
        "max_execution_ms": max(exec_times) if exec_times else 0,
        "min_execution_ms": min(exec_times) if exec_times else 0,
        "avg_results": round(sum(result_counts) / len(result_counts), 2) if result_counts else 0,
        "max_results": max(result_counts) if result_counts else 0,
        "min_results": min(result_counts) if result_counts else 0,
        "per_file_breakdown": files_seen,
    }

    try:
        Path(output_path).write_text(
            json.dumps(summary, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        logger.info("Saved summary.json → %s", output_path)
    except IOError as e:
        logger.error("Failed to write summary: %s", e)

    return summary


# ----------------------------
# Progress Display
# ----------------------------

def _print_progress(current: int, total: int, query: str, elapsed_ms: float, num_results: int) -> None:
    """Print a compact live progress line to stdout."""
    bar_len = 30
    filled = int(bar_len * current / total)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct = int(100 * current / total)
    short_query = query[:35].ljust(35)
    print(
        f"\r[{bar}] {pct:3d}% | {current:3d}/{total} | "
        f"{elapsed_ms:6.1f}ms | {num_results} results | {short_query}",
        end="",
        flush=True,
    )


# ----------------------------
# Main Orchestration
# ----------------------------

def run_benchmark(queries_dir: str = QUERIES_DIR_DEFAULT, top_k: int = TOP_K_DEFAULT) -> None:
    """Execute the full benchmark and generate all output reports.

    Args:
        queries_dir: Directory containing .txt benchmark query files.
        top_k: Max results per query.
    """
    logger.info("Starting Myboli AI Retrieval Benchmark")
    logger.info("Queries directory: %s | Top-K: %d", queries_dir, top_k)

    # 1. Load all query files
    query_files = load_query_files(queries_dir)
    if not query_files:
        logger.error("No query files found. Exiting.")
        return

    total_queries = sum(len(qs) for qs in query_files.values())
    logger.info("Total queries to evaluate: %d across %d files", total_queries, len(query_files))

    all_records: List[Dict[str, Any]] = []
    global_index = 0

    print(f"\n{'=' * 80}")
    print(f"  MYBOLI AI - RETRIEVAL BENCHMARK")
    print(f"  Queries: {total_queries} | Files: {len(query_files)} | Top-K: {top_k}")
    print(f"{'=' * 80}\n")

    # 2. Evaluate each query
    for filename, queries in query_files.items():
        logger.info("--- Evaluating file: %s (%d queries) ---", filename, len(queries))
        section_name = filename.replace("_", " ").title()

        for query in queries:
            global_index += 1
            try:
                record = evaluate_query(
                    query=query,
                    benchmark_file=filename,
                    section_name=section_name,
                    top_k=top_k,
                )
                all_records.append(record)
                _print_progress(global_index, total_queries, query, record["execution_ms"], record["num_results"])
            except Exception as e:
                logger.error("Unhandled error for query '%s': %s", query[:50], e)
                # Still record a failed entry so nothing is silently skipped
                all_records.append({
                    "timestamp": datetime.now().isoformat(),
                    "benchmark_file": filename,
                    "section_name": section_name,
                    "query": query,
                    "processed_query": "",
                    "detected_district": None,
                    "detected_category": None,
                    "detected_date": None,
                    "detected_persons": [],
                    "detected_events": [],
                    "final_search_string": query,
                    "top_k_requested": top_k,
                    "execution_ms": 0.0,
                    "num_results": 0,
                    "error": str(e),
                    "keywords": [],
                    "results": [],
                })

    print("\n")  # Newline after progress bar

    # 3. Write reports
    logger.info("Writing output reports...")
    write_json_report(all_records, OUTPUT_JSON)
    write_markdown_report(all_records, OUTPUT_MD)
    summary = write_summary_report(all_records, OUTPUT_SUMMARY)

    # 4. Print final summary
    print(f"\n{'=' * 60}")
    print(f"  BENCHMARK COMPLETE")
    print(f"{'=' * 60}")
    print(f"  Total Queries        : {summary['total_queries']}")
    print(f"  Successful           : {summary['successful_queries']}")
    print(f"  Failed               : {summary['failed_queries']}")
    print(f"  Zero-Result Queries  : {summary['zero_result_queries']}")
    print(f"  Avg Execution Time   : {summary['avg_execution_ms']} ms")
    print(f"  Avg Results          : {summary['avg_results']}")
    print(f"  Max Results          : {summary['max_results']}")
    print(f"  Min Results          : {summary['min_results']}")
    print(f"{'=' * 60}")
    print(f"  [JSON] benchmark_results.json")
    print(f"  [MD]   benchmark_results.md")
    print(f"  [JSON] summary.json")
    print(f"{'=' * 60}\n")


# ----------------------------
# CLI Entry Point
# ----------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Myboli AI — Marathi News Retrieval Benchmark Evaluator"
    )
    parser.add_argument(
        "--queries-dir",
        type=str,
        default=QUERIES_DIR_DEFAULT,
        help=f"Directory containing .txt benchmark query files (default: {QUERIES_DIR_DEFAULT})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K_DEFAULT,
        help=f"Maximum number of results to retrieve per query (default: {TOP_K_DEFAULT})",
    )
    args = parser.parse_args()
    run_benchmark(queries_dir=args.queries_dir, top_k=args.top_k)
