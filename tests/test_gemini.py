import logging
import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from gemini_service import generate_answer

logging.basicConfig(level=logging.INFO)

question = input("Question : ")

answer = generate_answer(question)

print("\n")
print(answer)