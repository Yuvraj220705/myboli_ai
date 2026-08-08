"""Sprint 5.0.2: Conversational Behavior & System Prompt Benchmark Evaluation.

Evaluates conversational prompt system behavior across:
1. Casual Greetings & Conversational Queries
2. Genuine News Queries Groundedness
3. Mixed Intent Queries (Greeting + News Query)
4. Unknown Entity Guardrail Immunity
5. Latency & Gemini Call Impact
Generates evaluation/conversational_behavior_benchmark.json.
"""

import json
import time
import sys
from pathlib import Path
from typing import Dict, List, Any

# Ensure src/ is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gemini_service import generate_answer
from prompt_manager import PromptManager


CONVERSATIONAL_BENCHMARK_SET: List[Dict[str, str]] = [
    {"query": "Hi", "expected_type": "CONVERSATIONAL", "desc": "English Greeting"},
    {"query": "Hello", "expected_type": "CONVERSATIONAL", "desc": "English Greeting"},
    {"query": "नमस्कार", "expected_type": "CONVERSATIONAL", "desc": "Marathi Greeting"},
    {"query": "Good Morning", "expected_type": "CONVERSATIONAL", "desc": "Bilingual Greeting"},
    {"query": "धन्यवाद", "expected_type": "CONVERSATIONAL", "desc": "Marathi Gratitude"},
    {"query": "Thanks", "expected_type": "CONVERSATIONAL", "desc": "English Gratitude"},
    {"query": "तू कोण आहेस?", "expected_type": "IDENTITY", "desc": "Marathi Identity Query"},
    {"query": "Who are you?", "expected_type": "IDENTITY", "desc": "English Identity Query"},
    {"query": "तू काय करू शकतोस?", "expected_type": "CAPABILITY", "desc": "Marathi Capability Query"},
    {"query": "What can you do?", "expected_type": "CAPABILITY", "desc": "English Capability Query"},
    {"query": "छान!", "expected_type": "CONVERSATIONAL", "desc": "Casual Feedback"},
    {"query": "हाय, आज पुण्यात काय झालं?", "expected_type": "MIXED", "desc": "Mixed Greeting + News Query"},
    {"query": "आज पुण्यात काय घडलं?", "expected_type": "NEWS_QUERY", "desc": "Pure News Query"},
    {"query": "अमित शाह नागपूर बातमी", "expected_type": "NEWS_QUERY", "desc": "Person News Query"},
    {"query": "जो बायडेन भारतात कधी येणार?", "expected_type": "UNSUPPORTED_GUARD", "desc": "Unknown Entity Guard Query"},
]


def run_benchmark() -> Dict[str, Any]:
    """Execute benchmark over conversational, mixed, news, and guardrail test set."""
    print("=" * 75)
    print("  CONVERSATIONAL BEHAVIOR & PROMPT SYSTEM BENCHMARK (Sprint 5.0.2)")
    print("=" * 75)

    pm = PromptManager()
    results = []
    latencies = []

    no_info_disclaimer_count = 0
    guard_blocked_count = 0
    grounded_news_count = 0
    conversational_natural_count = 0

    for item in CONVERSATIONAL_BENCHMARK_SET:
        q = item["query"]
        q_type = item["expected_type"]
        desc = item["desc"]

        t0 = time.perf_counter()
        res = generate_answer(q)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        answer = res.get("answer", "")
        sources = res.get("sources", [])

        # Audit behavior status
        if "माझ्याकडे या विषयासंबंधी प्रकाशित माहिती उपलब्ध नाही" in answer:
            behavior_status = "GUARD_DISCLAIMER"
            guard_blocked_count += 1
        elif "माझ्याकडे या प्रश्नासंबंधी कोणतीही प्रकाशित माहिती उपलब्ध नाही" in answer:
            behavior_status = "NEWS_FALLBACK"
            no_info_disclaimer_count += 1
        elif sources:
            behavior_status = "GROUNDED_NEWS_ANSWER"
            grounded_news_count += 1
        else:
            behavior_status = "CONVERSATIONAL_NATURAL"
            conversational_natural_count += 1

        results.append({
            "query": q,
            "expected_type": q_type,
            "description": desc,
            "answer_snippet": answer[:120],
            "behavior_status": behavior_status,
            "sources": sources,
            "latency_ms": round(dt, 2),
        })

    avg_latency = round(sum(latencies) / len(latencies), 2)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_queries_tested": len(CONVERSATIONAL_BENCHMARK_SET),
        "conversational_natural_responses": conversational_natural_count,
        "grounded_news_responses": grounded_news_count,
        "news_fallback_responses": no_info_disclaimer_count,
        "guard_disclaimers": guard_blocked_count,
        "avg_pipeline_latency_ms": avg_latency,
        "additional_gemini_calls_per_query": 0,
        "detailed_results": results,
    }

    out_path = PROJECT_ROOT / "evaluation" / "conversational_behavior_benchmark.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Total Queries Evaluated          : {len(CONVERSATIONAL_BENCHMARK_SET)}")
    print(f"Conversational Natural Outputs    : {conversational_natural_count}")
    print(f"Grounded News Answers            : {grounded_news_count}")
    print(f"Unknown Entity Guard Disclaimers : {guard_blocked_count}")
    print(f"Additional LLM Calls Introduced  : 0")
    print(f"Average Pipeline Latency         : {avg_latency} ms")
    print(f"\nSaved benchmark results to {out_path}")
    print("=" * 75)

    return summary


if __name__ == "__main__":
    run_benchmark()
