import logging
import sys
from pathlib import Path

# Add src to Python module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from retriever import search_articles

logging.basicConfig(level=logging.INFO)

query = input("Search : ")

results = search_articles(query)

print(f"\nFound {len(results)} articles\n")

for article in results:

    print("=" * 80)

    print("Title:")
    print(article["title"])

    print("\nScore:")
    print(article["score"])

    print("\nCategory:")
    print(article["category"])

    print("\nDistrict:")
    print(article["district"])

    print("\nPublished:")
    print(article["createdAt"])

    print("\nContent Preview:")
    print(article["content"][:250])

    print()