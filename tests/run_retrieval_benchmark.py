"""Automated Retrieval Benchmark Tool for Marathi RAG System.

Evaluates retrieval pipeline robustness against spelling variations and typos.
Does NOT call Gemini or generate answers.
"""

import csv
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Reconfigure stdout for UTF-8 on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from query_processor import process_query, DISTRICTS, CATEGORY_ALIASES
from retriever import search_articles

KNOWN_PERSONS = {
    "अमित शाह", "विनायक राऊत", "उदय सामंत", "एकनाथ शिंदे",
    "देवेंद्र फडणवीस", "अजित पवार", "उद्धव ठाकरे", "सचिन अहिर",
}

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("retrieval_benchmark")

# Benchmark dataset grouped by category
DATASET: Dict[str, List[str]] = {
    "Person: Amit Shah": [
        "अमीत शाह", "अमित शहा", "अमीत शहा", "अमीत साह", "अमित स्हा",
        "अमीतशाह", "अमित शाहा", "अमीत स्हा", "अमीत शाह पुणे", "अमीत शाह दौरा"
    ],
    "Person: Uddhav Thackeray": [
        "उध्दव ठाकरे", "उधव ठाकरे", "उद्दव ठाकरे", "उधव ठाकरें", "उध्दव ठाकरें",
        "उद्धव ठाकरे बातमी", "उधव मुख्यमंत्री", "उध्दव भाषण", "उध्दव पत्रकार परिषद", "उधव मुंबई"
    ],
    "Person: Devendra Fadnavis": [
        "देवेद्र फडणवीस", "देवेन्द्र फडणवीस", "देवेंद्र फडनवीस", "देवेद्र फडणवीस", "देवेंद्र फडणविस",
        "फडणविस", "फडणवीस पुणे", "देवेंद्र मुख्यमंत्री", "फडणवीस भाषण", "देवेंद्र बातमी"
    ],
    "Person: Ajit Pawar": [
        "अजीत पवार", "अजीत पवार", "अजित पावार", "अजीत पावार", "पवार बातमी",
        "अजीत भाषण", "अजीत पुणे", "पवार पत्रकार परिषद", "अजित सरकार", "अजित बैठक"
    ],
    "Person: Vinayak Raut": [
        "विनायक राउत", "विनायक रावत", "विनायक राऊत", "विनयक राऊत", "विनायक राउट",
        "राउत बातमी", "विनायक खासदार", "राऊत पत्रकार परिषद", "विनायक भाषण", "रावत बातमी"
    ],
    "District: Kolhapur": [
        "कोल्हापुर", "कोलापुर", "कोलहापूर", "कोलापूर", "कोल्हपुर",
        "कोल्हापुरात", "कोलापुर पाउस", "कोलापुर अपघात", "कोल्हापुर बातमी", "कोलापुर राजकारण"
    ],
    "District: Nagpur": [
        "नागपुर", "नागपुरा", "नागपुुर", "नागपूरात", "नागपुर पाउस",
        "नागपुर अपघात", "नागपुर बातमी", "नागपुर राजकारण", "नागपुर दुर्घटना", "नागपुर हवामान"
    ],
    "District: Pune": [
        "पुने", "पूणे", "पुण", "पुण्यात", "पुने बातमी",
        "पुने अपघात", "पुणे पाउस", "पुने राजकारण", "पुणे हवामान", "पुणे दौरा"
    ],
    "District: Sindhudurg": [
        "सिंदुदुर्ग", "सिधुदुर्ग", "सिध्दुदुर्ग", "सिंधुदूर्ग", "सिंदुदुर्गात",
        "सिंदुदुर्ग बातमी", "सिधुदुर्ग पाउस", "सिंदुदुर्ग अपघात", "सिधुदुर्ग राजकारण", "सिंदुदुर्ग हवामान"
    ],
    "General Typos & Misspellings": [
        "राजकरण", "राजकारन", "राज्कारण", "राजकरण बातमी", "राजकरण आज",
        "अपघत", "अपघाड", "पाउस", "शेतकारी", "मुख्य बातमी"
    ]
}

OUTPUT_CSV = Path(__file__).resolve().parent.parent / "evaluation" / "retrieval_benchmark_results.csv"

def classify_status(num_articles: int, top_score: float) -> str:
    """Classify retrieval status into PASS, PARTIAL, or FAIL.

    - PASS: 3+ articles retrieved or strong match score
    - PARTIAL: 1-2 articles retrieved
    - FAIL: 0 articles retrieved
    """
    if num_articles >= 3 or top_score >= 1.0:
        return "PASS"
    elif num_articles >= 1:
        return "PARTIAL"
    else:
        return "FAIL"

def run_benchmark():
    records = []
    category_stats: Dict[str, Dict[str, Any]] = {}

    print("=" * 80)
    print("  MARATHI RETRIEVAL SPELLING & TYPO BENCHMARK")
    print("  Evaluating Retrieval Pipeline (No Gemini calls)")
    print("=" * 80)

    total_queries = 0
    total_time_ms = 0.0
    total_articles = 0
    status_counts = {"PASS": 0, "PARTIAL": 0, "FAIL": 0}

    for cat_name, queries in DATASET.items():
        category_stats[cat_name] = {
            "total": len(queries),
            "PASS": 0,
            "PARTIAL": 0,
            "FAIL": 0,
            "total_time_ms": 0.0,
            "total_articles": 0,
        }

        for q in queries:
            total_queries += 1
            start_t = time.perf_counter()

            # 1. Process query
            try:
                q_info = process_query(q)
            except Exception as e:
                logger.error("Error processing query '%s': %s", q, e)
                q_info = None

            # 2. Execute retrieval (Skip Gemini)
            try:
                articles = search_articles(q, top_k=5)
            except Exception as e:
                logger.error("Error retrieving for query '%s': %s", q, e)
                articles = []

            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 2)

            # Metadata extraction
            proc_query = q_info.clean_query if q_info else ""
            intent = "latest_news" if (q_info and q_info.is_latest_news) else "search"
            dist = q_info.district if q_info else None
            cat_detected = q_info.category if q_info else None
            dt_detected = str(q_info.date) if (q_info and q_info.date) else None
            
            # Detect person name if mentioned
            person = None
            if q_info:
                for p in KNOWN_PERSONS:
                    if p.split()[0] in q:
                        person = p
                        break

            # Article details
            num_arts = len(articles)
            source_ids = [str(a["id"]) for a in articles if "id" in a]
            top_title = articles[0]["title"] if articles else ""
            top_score = round(float(articles[0].get("score", 0.0)), 4) if articles else 0.0

            status = classify_status(num_arts, top_score)

            # Accumulate statistics
            status_counts[status] += 1
            total_time_ms += elapsed_ms
            total_articles += num_arts

            category_stats[cat_name][status] += 1
            category_stats[cat_name]["total_time_ms"] += elapsed_ms
            category_stats[cat_name]["total_articles"] += num_arts

            records.append({
                "Query": q,
                "Category": cat_name,
                "ProcessedQuery": proc_query,
                "Intent": intent,
                "Person": person or "",
                "District": dist or "",
                "CategoryDetected": cat_detected or "",
                "Date": dt_detected or "",
                "NumArticles": num_arts,
                "SourceIDs": ";".join(source_ids),
                "TopArticle": top_title,
                "Score": top_score,
                "ExecutionTimeMs": elapsed_ms,
                "Status": status,
            })

            print(f"[{status:7s}] {q[:25]:25s} | {num_arts} articles | {elapsed_ms:6.1f}ms | Top: {top_title[:35]}")

    # Write CSV
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as csvfile:
        fieldnames = [
            "Query", "Category", "ProcessedQuery", "Intent", "Person",
            "District", "CategoryDetected", "Date", "NumArticles",
            "SourceIDs", "TopArticle", "Score", "ExecutionTimeMs", "Status"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    avg_time = round(total_time_ms / total_queries, 2) if total_queries else 0
    avg_arts = round(total_articles / total_queries, 2) if total_queries else 0

    print("\n" + "=" * 80)
    print("  RETRIEVAL BENCHMARK SUMMARY")
    print("=" * 80)
    print(f"Total Queries Evaluated : {total_queries}")
    print(f"PASS                    : {status_counts['PASS']} ({status_counts['PASS']/total_queries*100:.1f}%)")
    print(f"PARTIAL                 : {status_counts['PARTIAL']} ({status_counts['PARTIAL']/total_queries*100:.1f}%)")
    print(f"FAIL                    : {status_counts['FAIL']} ({status_counts['FAIL']/total_queries*100:.1f}%)")
    print(f"Average Retrieval Time  : {avg_time} ms")
    print(f"Average Articles        : {avg_arts}")
    print("=" * 80)

    print("\nCATEGORY-WISE BREAKDOWN:")
    print(f"{'Category':32s} | {'Total':5s} | {'PASS':5s} | {'PARTIAL':7s} | {'FAIL':5s} | {'Avg Time':8s} | {'Avg Arts':8s}")
    print("-" * 80)
    for cat_name, stats in category_stats.items():
        c_tot = stats["total"]
        c_pass = stats["PASS"]
        c_part = stats["PARTIAL"]
        c_fail = stats["FAIL"]
        c_avg_t = round(stats["total_time_ms"] / c_tot, 1) if c_tot else 0
        c_avg_a = round(stats["total_articles"] / c_tot, 1) if c_tot else 0
        print(f"{cat_name:32s} | {c_tot:5d} | {c_pass:5d} | {c_part:7d} | {c_fail:5d} | {c_avg_t:6.1f}ms | {c_avg_a:8.1f}")

    print("=" * 80)
    print(f"Saved benchmark results to {OUTPUT_CSV}")

if __name__ == "__main__":
    run_benchmark()
