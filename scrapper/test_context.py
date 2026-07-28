"""Manual test script for context building from retrieved articles."""

import logging

from gemini_service import build_context

logging.basicConfig(level=logging.INFO)

question = input("Question : ")

context = build_context(question)

print(context)