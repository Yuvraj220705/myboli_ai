"""Sprint 2.0.1: Context Builder Layer for Maayboli AI.

Provides a dedicated, reusable interface between the retriever and Gemini service.
Prepares, validates, deduplicates, truncates, and formats retrieved article metadata and content
into structured ContextPackage objects for LLM context injection.
"""

from dataclasses import dataclass, field
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Configurable Constants
MAX_CONTEXT_ARTICLES: int = 5
MAX_CONTEXT_CHARACTERS: int = 8000
APPROX_CHARS_PER_TOKEN: float = 4.0

__all__ = [
    "ContextArticle",
    "ContextPackage",
    "ContextBuilder",
    "MAX_CONTEXT_ARTICLES",
    "MAX_CONTEXT_CHARACTERS",
]


@dataclass(frozen=True)
class ContextArticle:
    """Cleaned and validated context article representation.

    Attributes:
        id: Unique article database ID.
        title: Article title string.
        content: Article body text string.
        district: Optional district name.
        category: Optional category name.
        date: Optional published date string or date object.
        url: Optional article URL string.
    """
    id: int
    title: str
    content: str
    district: Optional[str] = None
    category: Optional[str] = None
    date: Optional[str] = None
    url: Optional[str] = None


@dataclass
class ContextPackage:
    """Structured context payload generated for LLM consumption.

    Attributes:
        formatted_context: Human-readable structured text ready for prompt injection.
        articles: List of ContextArticle instances included in the context.
        sources: List of lightweight source metadata dicts.
        article_count: Number of articles included.
        estimated_tokens: Estimated token count for the formatted context.
        total_characters: Total character count of formatted context.
        is_truncated: Flag indicating if context was truncated due to character limits.
    """
    formatted_context: str
    articles: List[ContextArticle] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    article_count: int = 0
    estimated_tokens: int = 0
    total_characters: int = 0
    is_truncated: bool = False


class ContextBuilder:
    """Dedicated Context Builder layer for structuring retrieved news articles."""

    def __init__(
        self,
        max_articles: int = MAX_CONTEXT_ARTICLES,
        max_characters: int = MAX_CONTEXT_CHARACTERS,
    ):
        """Initialize ContextBuilder with configurable limits.

        Args:
            max_articles: Maximum number of articles to include (default: 5).
            max_characters: Maximum total character length of formatted context (default: 8000).
        """
        self.max_articles = max_articles
        self.max_characters = max_characters

    def build_context(self, raw_articles: Optional[List[Dict[str, Any]]]) -> ContextPackage:
        """Process, deduplicate, validate, format, and package retrieved article dicts.

        Args:
            raw_articles: List of raw article dictionaries from retriever.

        Returns:
            ContextPackage containing formatted context and metadata metrics.
        """
        if not raw_articles:
            return ContextPackage(
                formatted_context="",
                articles=[],
                sources=[],
                article_count=0,
                estimated_tokens=0,
                total_characters=0,
                is_truncated=False,
            )

        seen_ids = set()
        deduped_articles: List[ContextArticle] = []
        sources: List[Dict[str, Any]] = []

        # 1. Deduplicate by ID while preserving retrieval ranking order
        for item in raw_articles:
            if not isinstance(item, dict):
                continue

            art_id = item.get("id")
            if art_id is None or art_id in seen_ids:
                continue

            seen_ids.add(art_id)

            title = (item.get("title") or "").strip()
            content = (item.get("content") or "").strip()

            # Skip empty articles (where both title and content are missing)
            if not title and not content:
                continue

            district = item.get("district") or item.get("district_name")
            category = item.get("category") or item.get("category_name")
            pub_date = item.get("createdAt") or item.get("date") or item.get("published_at")
            url = item.get("url") or item.get("link")

            ctx_art = ContextArticle(
                id=int(art_id),
                title=title,
                content=content,
                district=str(district).strip() if district else None,
                category=str(category).strip() if category else None,
                date=str(pub_date).strip() if pub_date else None,
                url=str(url).strip() if url else None,
            )

            deduped_articles.append(ctx_art)

            src_entry: Dict[str, Any] = {
                "id": ctx_art.id,
                "title": ctx_art.title,
            }
            if ctx_art.district:
                src_entry["district"] = ctx_art.district
            if ctx_art.category:
                src_entry["category"] = ctx_art.category
            if ctx_art.date:
                src_entry["date"] = ctx_art.date
            if ctx_art.url:
                src_entry["url"] = ctx_art.url

            sources.append(src_entry)

            if len(deduped_articles) >= self.max_articles:
                break

        # 2. Format articles into structured text blocks & enforce character limits
        parts: List[str] = []
        included_articles: List[ContextArticle] = []
        included_sources: List[Dict[str, Any]] = []
        current_length = 0
        is_truncated = False

        for i, art in enumerate(deduped_articles, start=1):
            lines = [
                f"--- Article {i} (ID: {art.id}) ---",
                f"Title: {art.title}",
            ]
            if art.category:
                lines.append(f"Category: {art.category}")
            if art.district:
                lines.append(f"District: {art.district}")
            if art.date:
                lines.append(f"Published Date: {art.date}")
            if art.url:
                lines.append(f"URL: {art.url}")

            lines.append(f"Content: {art.content}")

            block_text = "\n".join(lines)
            needed_len = len(block_text) + (2 if parts else 0)

            if current_length + needed_len > self.max_characters:
                rem_chars = self.max_characters - current_length - (2 if parts else 0)
                if rem_chars > 200:
                    truncated_content = art.content[: rem_chars - 100] + " ... [Truncated]"
                    lines[-1] = f"Content: {truncated_content}"
                    block_text = "\n".join(lines)
                    parts.append(block_text)
                    included_articles.append(art)
                    included_sources.append(sources[i - 1])
                    current_length += len(block_text)
                is_truncated = True
                break

            parts.append(block_text)
            included_articles.append(art)
            included_sources.append(sources[i - 1])
            current_length += needed_len

        formatted_str = "\n\n".join(parts)
        total_chars = len(formatted_str)
        estimated_tokens = int(total_chars / APPROX_CHARS_PER_TOKEN)

        logger.info(
            "Built ContextPackage: articles=%d/%d, total_chars=%d, estimated_tokens=%d, truncated=%s",
            len(included_articles),
            len(raw_articles),
            total_chars,
            estimated_tokens,
            is_truncated,
        )

        return ContextPackage(
            formatted_context=formatted_str,
            articles=included_articles,
            sources=included_sources,
            article_count=len(included_articles),
            estimated_tokens=estimated_tokens,
            total_characters=total_chars,
            is_truncated=is_truncated,
        )
