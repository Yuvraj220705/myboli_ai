"""Live Demo Script — 15 mixed queries (PASS + FAIL) for code review meeting.

Run while app.py is running:
    python tests/demo_queries.py
"""

import json
import requests
import sys

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "http://localhost:5000/chatbot/ask"

# 15 queries: mix of successful retrievals and known failure cases
DEMO_QUERIES = [
    # --- SUCCESSFUL QUERIES (should return good answers) ---
    ("अमित शाह यांच्या दौऱ्याबद्दल काय बातमी आहे?",        "✅ Person search — exact spelling"),
    ("उद्धव ठाकरे बातमी",                                     "✅ Person search — correct name"),
    ("देवेंद्र फडणवीस",                                        "✅ Person search — CM name"),
    ("कोल्हापूर",                                               "✅ District search — correct spelling"),
    ("राजकारण",                                                "✅ Category search — Politics"),
    ("आज काय घडलं?",                                           "✅ Latest news intent"),
    ("नागपुर अपघात",                                           "✅ District + keyword combo"),
    ("अजित पवार",                                              "✅ Person search — Ajit Pawar"),

    # --- FAILURE QUERIES (known gaps — typos/misspellings) ---
    ("अमीत साह",                                               "❌ Severe typo — शाह → साह"),
    ("कोलापुर",                                                "❌ District misspelling — missing ल्ह"),
    ("राजकरण",                                                 "❌ Category typo — missing ा matra"),
    ("उधव मुंबई",                                              "❌ Short name + district filter = 0"),
    ("पुण्यात अपघात",                                          "❌ Suffix variation — पुण्यात vs पुणे"),
    ("अपघत",                                                   "❌ Keyword typo — missing ा"),
    ("शेतकारी",                                                "❌ Keyword typo — शेतकारी vs शेतकरी"),
]

print("=" * 70)
print("  MAAYBOLI AI — LIVE DEMO (15 Queries)")
print("  Retriever + Gemini 1.5 Flash RAG Pipeline")
print("=" * 70)

for i, (query, label) in enumerate(DEMO_QUERIES, 1):
    print(f"\n{'─' * 70}")
    print(f"  Query {i}/15: {query}")
    print(f"  Type: {label}")
    print(f"{'─' * 70}")

    try:
        resp = requests.post(URL, json={"question": query, "session_id": "demo"}, timeout=30)
        data = resp.json()

        answer = data.get("answer", "No answer returned")
        sources = data.get("sources", [])

        # Truncate answer for clean display
        display_answer = answer[:300] + "..." if len(answer) > 300 else answer

        print(f"\n  📝 Answer:\n  {display_answer}")

        if sources:
            print(f"\n  📰 Sources ({len(sources)}):")
            for s in sources[:3]:
                title = s.get("title", "N/A")[:80]
                print(f"     • {title}")
        else:
            print("\n  📰 Sources: None returned")

    except requests.ConnectionError:
        print("\n  ⚠️  ERROR: Cannot connect to server. Is app.py running?")
        print("     Run: python app.py")
        break
    except Exception as e:
        print(f"\n  ⚠️  ERROR: {e}")

print(f"\n{'=' * 70}")
print("  DEMO COMPLETE")
print(f"{'=' * 70}")
