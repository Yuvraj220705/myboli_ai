"""Gemini AI service for prompt construction and grounded answer generation."""

import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from google import genai

from context_builder import ContextBuilder, ContextPackage
from retriever import search_articles

load_dotenv()

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
NO_ARTICLES_MSG = "माझ्याकडे या प्रश्नासंबंधी कोणतीही प्रकाशित माहिती उपलब्ध नाही."
ERROR_MSG = "माहिती मिळवताना तांत्रिक अडचण आली. कृपया नंतर पुन्हा प्रयत्न करा."

# Initialize ContextBuilder instance
_context_builder = ContextBuilder()

# Initialize Gemini Client safely
_api_key = os.getenv("GEMINI_API_KEY")
if not _api_key:
    logger.warning("GEMINI_API_KEY environment variable is not configured.")

client = None
if _api_key:
    try:
        client = genai.Client(api_key=_api_key)
    except Exception as e:
        logger.error("Failed to initialize Gemini Client: %s", e)


def build_context(articles: List[Dict[str, Any]], query: Optional[str] = None) -> str:
    """Construct prompt context string strictly using ContextBuilder.

    Args:
        articles: List of article dicts retrieved from the database.
        query: Optional user question string for query-relevant snippet scoring.

    Returns:
        str: Formatted context string containing article information.
    """
    pkg = _context_builder.build_context(articles, query=query)
    return pkg.formatted_context


def generate_answer(question: str, top_k: int = 5) -> Dict[str, Any]:
    """Generate grounded answer using strictly retrieved articles and Gemini API.

    Args:
        question: User query string.
        top_k: Number of articles to retrieve from database.

    Returns:
        Dict[str, Any]: Dictionary containing 'answer' (str) and 'sources' (list of article IDs).
    """
    if not question or not question.strip():
        return {
            "answer": "कृपया एक वैध प्रश्न विचार.",
            "sources": [],
        }

    clean_question = question.strip()

    # 1. Retrieve articles via retriever
    try:
        articles = search_articles(clean_question, top_k=top_k)
    except Exception as e:
        logger.error("Retrieval execution error for question '%s': %s", clean_question[:50], e, exc_info=True)
        return {
            "answer": ERROR_MSG,
            "sources": [],
        }

    # 2. Handle empty retrieval result
    if not articles:
        logger.info("No matching published articles found for: '%s'", clean_question[:50])
        return {
            "answer": NO_ARTICLES_MSG,
            "sources": [],
        }

    # 3. Build structured ContextPackage using Intelligent ContextBuilder
    context_pkg = _context_builder.build_context(articles, query=clean_question)
    source_ids = [s["id"] for s in context_pkg.sources]

    prompt = f"""You are an AI news assistant for Maayboli Malvani News.

STRICT GROUNDING RULES:
1. Answer the question ONLY using the factual details provided in the retrieved articles below.
2. Never use any external knowledge, prior training data, or outside facts. Never fabricate or extrapolate information.
3. If the answer cannot be completely derived from the retrieved articles, respond EXACTLY with: "{NO_ARTICLES_MSG}"
4. Present the response clearly in Marathi language.
5. Synthesize details from multiple articles if relevant, but do NOT add unmentioned details.

Retrieved Articles:
{context_pkg.formatted_context}

User Question:
{clean_question}
"""

    # 4. Invoke Gemini API model with error handling
    if client is None:
        logger.error("Gemini API client is not initialized.")
        return {
            "answer": ERROR_MSG,
            "sources": source_ids,
        }

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )

        answer_text = response.text.strip() if response and response.text else NO_ARTICLES_MSG

        # If answer indicates no relevant published info was found, clear source IDs
        if NO_ARTICLES_MSG in answer_text:
            return {
                "answer": NO_ARTICLES_MSG,
                "sources": [],
            }

        logger.info("Generated grounded answer for question: '%s'", clean_question[:50])
        return {
            "answer": answer_text,
            "sources": source_ids,
        }
    except Exception as e:
        logger.error("Gemini API request failed: %s", e, exc_info=True)
        return {
            "answer": ERROR_MSG,
            "sources": source_ids,
        }