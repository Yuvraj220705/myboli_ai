"""Manual test script for FULLTEXT article search."""

import logging

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

    print("\nPublished:")
    print(article["published_at"])

    print("\nBody Preview:")
    print(article["body"][:250])

    print("\nURL:")
    print(article["article_url"])

    print()