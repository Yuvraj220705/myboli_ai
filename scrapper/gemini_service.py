"""Gemini AI service for answering questions using retrieved articles."""

import logging
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai

from retriever import search_articles

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
NO_ANSWER_MSG = "माझ्याकडे या प्रश्नासंबंधी पुरेशी माहिती उपलब्ध नाही."

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def build_context(question: str) -> Optional[str]:
    """Build context string from retrieved articles.

    Args:
        question: The user's question for article retrieval.

    Returns:
        A formatted context string, or None if no articles found.
    """
    articles = search_articles(question)

    if not articles:
        return None

    parts = []

    for i, article in enumerate(articles, start=1):
        lines = [f"Article {i}", f"Title:\n{article['title']}"]

        if article.get("category"):
            lines.append(f"Category:\n{article['category']}")
        if article.get("district"):
            lines.append(f"District:\n{article['district']}")
        if article.get("createdAt"):
            lines.append(f"Published:\n{article['createdAt']}")

        lines.append(f"Content:\n{article['content']}")
        lines.append("—" * 40)

        parts.append("\n\n".join(lines))

    return "\n\n".join(parts)


def generate_answer(question: str) -> str:
    """Generate an answer to a question using retrieved context and Gemini.

    Args:
        question: The user's question in Marathi or English.

    Returns:
        The generated answer string.
    """
    if not question or not question.strip():
        return NO_ANSWER_MSG

    context = build_context(question)

    if context is None:
        logger.info("No context found for question: %s", question[:80])
        return NO_ANSWER_MSG

    prompt = f"""You are a Marathi news assistant for a regional news platform.

Rules:
1. Answer ONLY using the retrieved articles provided below.
2. Do NOT use any external or prior knowledge. Never hallucinate.
3. If the answer is not available in the articles, reply EXACTLY with: "{NO_ANSWER_MSG}"
4. If multiple articles answer the question, combine their information into one coherent response.
5. Mention dates naturally when they are relevant to the answer.
6. Mention category or district naturally when they help answer the question.
7. Always answer in Marathi.
8. Never add assumptions, guesses, or information not present in the articles.

Retrieved Articles:

{context}

User Question:

{question}
"""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        logger.info("Gemini response generated for: %s", question[:80])
        return response.text or NO_ANSWER_MSG
    except Exception as e:
        logger.error("Gemini API error: %s", e)
        return NO_ANSWER_MSG