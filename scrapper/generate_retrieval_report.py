"""Generate a detailed Markdown report showing the exact articles retrieved for each query.
"""

import sys
import time
from pathlib import Path
from typing import Dict, List

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from query_processor import process_query
from retriever import search_articles
from run_retrieval_benchmark import DATASET, classify_status

REPORT_FILE = "retrieval_benchmark_detailed_report.md"

def generate_report():
    lines: List[str] = []
    
    lines.append("# Marathi News Retrieval — Detailed Query-by-Query Report\n")
    lines.append("> **Note**: This document records the exact articles retrieved from the database for each query variation in the retrieval benchmark.\n")
    lines.append("---\n")
    lines.append("## Executive Summary\n")
    lines.append("- **Total Queries**: 100")
    lines.append("- **Evaluation Metric**: MySQL FULLTEXT Retrieval + Intent Filtering")
    lines.append("- **Timestamp**: 2026-07-31\n")
    lines.append("---\n")

    query_counter = 0

    for category, queries in DATASET.items():
        lines.append(f"## Category: {category}\n")

        for q in queries:
            query_counter += 1
            start_t = time.perf_counter()
            q_info = process_query(q)
            articles = search_articles(q, top_k=5)
            elapsed_ms = round((time.perf_counter() - start_t) * 1000, 1)

            top_score = float(articles[0].get("score", 0.0)) if articles else 0.0
            status = classify_status(len(articles), top_score)

            status_badge = "🟢 **PASS**" if status == "PASS" else ("🟡 **PARTIAL**" if status == "PARTIAL" else "🔴 **FAIL**")

            lines.append(f"### {query_counter}. Query: `{q}`")
            lines.append(f"- **Status**: {status_badge}")
            lines.append(f"- **Processed Query**: `{q_info.clean_query}`")
            lines.append(f"- **Intent / Flags**: Latest News={q_info.is_latest_news}")
            lines.append(f"- **Detected Metadata**: District=`{q_info.district}`, Category=`{q_info.category}`, Date=`{q_info.date}`")
            lines.append(f"- **Articles Retrieved**: `{len(articles)}` (Execution Time: `{elapsed_ms} ms`)")
            lines.append("")
            lines.append("#### Fetched Articles:")

            if not articles:
                lines.append("_No matching published articles retrieved from database._\n")
            else:
                for idx, art in enumerate(articles, 1):
                    art_id = art.get("id", "N/A")
                    title = art.get("title", "").strip()
                    art_cat = art.get("category") or "N/A"
                    art_dist = art.get("district") or "N/A"
                    created_at = art.get("createdAt") or "N/A"
                    score = art.get("score")
                    score_str = f" (Score: `{score:.4f}`)" if score is not None else ""

                    content = art.get("content", "").replace("\n", " ").strip()
                    snippet = content[:200] + "..." if len(content) > 200 else content

                    lines.append(f"{idx}. **[ID: {art_id}]** **{title}**{score_str}")
                    lines.append(f"   - *Category*: {art_cat} | *District*: {art_dist} | *Date*: {created_at}")
                    lines.append(f"   - *Content Snippet*: \"{snippet}\"")
                lines.append("")

            lines.append("---\n")

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Successfully generated detailed report: {REPORT_FILE}")

if __name__ == "__main__":
    generate_report()
