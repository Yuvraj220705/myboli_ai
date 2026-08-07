"""Gemini AI service for prompt construction and grounded answer generation."""

import logging
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

from context_builder import ContextBuilder, ContextPackage
from conversation_router import ConversationRouter
from generation_engine import GenerationEngine
from intent_validator import IntentValidator, IntentValidationResult
from prompt_manager import PromptManager
from prompt_templates import ERROR_MSG, INVALID_QUERY_MSG, NO_ARTICLES_MSG
from query_processor import process_query
from retriever import search_articles

load_dotenv()

logger = logging.getLogger(__name__)

# Initialize pipeline singletons
_conversation_router = ConversationRouter()
_context_builder = ContextBuilder()
_intent_validator = IntentValidator()
_prompt_manager = PromptManager()
_generation_engine = GenerationEngine(prompt_manager=_prompt_manager)


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
    """Generate grounded answer using complete production RAG pipeline and Generation Engine.

    Pipeline Flow:
    User Question ➔ ConversationRouter ➔ QueryProcessor ➔ Retriever ➔ ContextBuilder ➔ IntentValidator ➔ GenerationEngine ➔ Grounded Answer

    Args:
        question: User query string.
        top_k: Number of articles to retrieve from database.

    Returns:
        Dict[str, Any]: Dictionary containing 'answer', 'sources', 'validation', and 'prompt_version'.
    """
    if not question or not question.strip():
        return {
            "answer": INVALID_QUERY_MSG,
            "sources": [],
            "validation": None,
            "prompt_version": _prompt_manager.default_version,
        }

    clean_question = question.strip()

    # 0. Conversation Routing check (Sprint 5.0.1)
    route = _conversation_router.route_message(clean_question)
    if not route.should_use_rag:
        return {
            "answer": route.response_text,
            "sources": [],
            "validation": None,
            "prompt_version": "conversational_v1",
            "intent_type": route.intent_type,
        }

    # 1. Process query to extract metadata & normalized query string
    query_info = process_query(clean_question)
    normalized_query_str = query_info.clean_query if query_info and query_info.clean_query else clean_question

    # 2. Retrieve articles via retriever
    try:
        articles = search_articles(clean_question, top_k=top_k)
    except Exception as e:
        logger.error("Retrieval execution error for question '%s': %s", clean_question[:50], e, exc_info=True)
        return {
            "answer": ERROR_MSG,
            "sources": [],
            "validation": None,
            "prompt_version": _prompt_manager.default_version,
        }

    # 3. Handle empty retrieval result
    if not articles:
        logger.info("No matching published articles found for: '%s'", clean_question[:50])
        empty_pkg = _context_builder.build_context([])
        val_res = _intent_validator.validate(query_info, empty_pkg)
        return {
            "answer": NO_ARTICLES_MSG,
            "sources": [],
            "validation": val_res,
            "prompt_version": _prompt_manager.default_version,
        }

    # 4. Build structured ContextPackage using Intelligent ContextBuilder
    context_pkg = _context_builder.build_context(articles, query=normalized_query_str)

    # 5. Run Intent Validation Quality Gate
    validation_res = _intent_validator.validate(query_info, context_pkg)

    # 6. Delegate Generation to GenerationEngine
    return _generation_engine.generate(
        question=clean_question,
        context_pkg=context_pkg,
        validation_result=validation_res,
    )