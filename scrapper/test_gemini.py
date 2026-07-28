"""Manual test script for full Gemini Q&A pipeline."""

import logging

from gemini_service import generate_answer

logging.basicConfig(level=logging.INFO)

question = input("Question : ")

answer = generate_answer(question)

print("\n")
print(answer)