"""Interactive CLI tool to run the full Marathi RAG Pipeline (Retriever + Context Builder + Gemini)."""

import logging
import os
from pathlib import Path
import sys

# Configure UTF-8 encoding for Windows terminals
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gemini_service import generate_answer

# Suppress debug log clutter for interactive CLI
logging.getLogger("query_processor").setLevel(logging.WARNING)
logging.getLogger("retriever").setLevel(logging.WARNING)
logging.getLogger("entity_normalizer").setLevel(logging.WARNING)
logging.getLogger("context_builder").setLevel(logging.WARNING)
logging.getLogger("gemini_service").setLevel(logging.WARNING)


def main():
    print("=" * 80)
    print("🤖 MAAYBOLI MARATHI RAG NEWS CHATBOT (Retriever + Context Builder + Gemini)")
    print("=" * 80)
    print("Type your Marathi news question below (e.g. 'आज पुण्यात अमित शाह काय म्हणाले?').")
    print("Type 'exit' or 'quit' to exit.\n")

    while True:
        try:
            user_input = input("❓ विचार (Question): ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "बाहेर"]:
                print("👋 Thank you for using Maayboli AI Chatbot!")
                break

            result = generate_answer(user_input)

            if result.get("intent_type"):
                print("\n" + "-" * 80)
                print("🤖 उत्तर (Maayboli AI Response):")
                print(result["answer"])
                print("-" * 80 + "\n")
                continue

            val = result.get("validation")
            if val:
                print(f"🛡️  Intent Quality Gate: [{val.retrieval_status}] (Confidence: {val.confidence}, Score: {val.overall_match_score}%)")
                print(f"   Reason: {val.validation_reason}")

            print("\n" + "-" * 80)
            print("💡 उत्तर (Gemini Grounded Answer):")
            print(result["answer"])
            print("-" * 80)
            if result.get("sources"):
                print(f"📌 Source Article IDs: {result['sources']}")
            print("=" * 80 + "\n")

        except KeyboardInterrupt:
            print("\n👋 Exiting...")
            break
        except Exception as e:
            print(f"\n❌ Error executing pipeline: {e}\n")


if __name__ == "__main__":
    main()
