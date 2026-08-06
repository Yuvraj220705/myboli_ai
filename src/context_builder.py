"""Sprint 2.0.2: Intelligent Context Engineering (Snippet Extraction) for Maayboli AI.

Provides a dedicated, reusable interface between the retriever and Gemini service.
Prepares, validates, deduplicates, extracts relevant paragraph snippets, and packages
structured ContextPackage objects with token compression metrics for LLM context injection.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Set
from entity_normalizer import normalize_unicode

logger = logging.getLogger(__name__)

# Configurable Constants
MAX_CONTEXT_ARTICLES: int = 5
MAX_CONTEXT_CHARACTERS: int = 8000
APPROX_CHARS_PER_TOKEN: float = 4.0

# Noise / Boilerplate Regex Patterns to filter out
BOILERPLATE_PATTERNS: List[re.Pattern] = [
    re.compile(r"जाहिरात", re.IGNORECASE),
    re.compile(r"subscribe", re.IGNORECASE),
    re.compile(r"copyright", re.IGNORECASE),
    re.compile(r"सर्वाधिक वाचलेल्या", re.IGNORECASE),
    re.compile(r"ताजी बातमी", re.IGNORECASE),
    re.compile(r"click here", re.IGNORECASE),
    re.compile(r"all rights reserved", re.IGNORECASE),
    re.compile(r"फॉलो करा", re.IGNORECASE),
]

__all__ = [
    "ContextArticle",
    "ContextPackage",
    "ContextBuilder",
    "MAX_CONTEXT_ARTICLES",
    "MAX_CONTEXT_CHARACTERS",
    "extract_snippets",
]


@dataclass(frozen=True)
class ContextArticle:
    """Cleaned and validated context article representation.

    Attributes:
        id: Unique article database ID.
        title: Article title string.
        content: Article body text string or extracted snippet text.
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
        article_count: Number of articles included in context.
        original_article_count: Number of raw articles retrieved.
        snippet_count: Total number of paragraph snippets extracted across articles.
        characters_before: Total character count before snippet extraction.
        characters_after: Total character count of formatted context.
        estimated_tokens_before: Estimated token count before snippet extraction.
        estimated_tokens_after: Estimated token count of formatted context.
        compression_ratio: Percentage reduction in character size.
        total_characters: Total character count of formatted context.
        estimated_tokens: Estimated token count for formatted context.
        is_truncated: Flag indicating if context was truncated due to character limits.
    """
    formatted_context: str
    articles: List[ContextArticle] = field(default_factory=list)
    sources: List[Dict[str, Any]] = field(default_factory=list)
    article_count: int = 0
    original_article_count: int = 0
    snippet_count: int = 0
    characters_before: int = 0
    characters_after: int = 0
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0
    compression_ratio: float = 0.0
    total_characters: int = 0
    estimated_tokens: int = 0
    is_truncated: bool = False


def _is_boilerplate(paragraph: str) -> bool:
    """Check if a paragraph is meaningless noise or boilerplate text."""
    clean = paragraph.strip()
    if not clean or len(clean) < 15:
        return True
    for pattern in BOILERPLATE_PATTERNS:
        if pattern.search(clean):
            return True
    return False


def extract_snippets(
    content: str,
    query: Optional[str] = None,
    top_n_paragraphs: int = 2,
    window_expansion: int = 1,
) -> str:
    """Extract query-relevant paragraph snippets with a ±1 paragraph window.

    Deterministic Flow:
    1. Split content into paragraphs & filter out boilerplate.
    2. Score each paragraph based on query keyword overlap, lead position bias, & length.
    3. Select top N highest-scoring paragraphs.
    4. Expand window by ±1 neighboring paragraph.
    5. Join selected paragraphs in original chronological order.

    Args:
        content: Raw article content body text.
        query: Optional user query string.
        top_n_paragraphs: Top scoring paragraphs to select (default: 2).
        window_expansion: Neighboring paragraph expansion size (default: 1).

    Returns:
        Extracted snippet text string.
    """
    if not content or not content.strip():
        return ""

    # Split into paragraphs by double newlines or single newlines
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n|\n", content) if p.strip()]
    paras = [p for p in raw_paras if not _is_boilerplate(p)]

    if not paras:
        # Fallback if all paras filtered
        return content.strip()[:1000]

    if len(paras) <= top_n_paragraphs + window_expansion:
        # Article is short enough; return clean joined paragraphs
        return "\n\n".join(paras)

    # Tokenize and normalize query keywords
    query_tokens: Set[str] = set()
    if query:
        norm_query = normalize_unicode(query.lower())
        query_tokens = set(re.findall(r"[\w\u0900-\u097F]+", norm_query))

    # Score each paragraph
    scored_paras: List[tuple[int, float]] = []  # (index, score)

    for idx, para in enumerate(paras):
        norm_para = normalize_unicode(para.lower())
        para_words = set(re.findall(r"[\w\u0900-\u097F]+", norm_para))

        score = 0.0
        # 1. Query Keyword Overlap Score
        if query_tokens:
            overlap = len(query_tokens.intersection(para_words))
            score += overlap * 3.0

        # 2. Lead Paragraph Position Bias (News Inverted Pyramid)
        if idx == 0:
            score += 2.0  # Lead paragraph bonus
        elif idx == 1:
            score += 1.0  # Second paragraph bonus

        # 3. Substantial Paragraph Length Bonus
        if 50 <= len(para) <= 400:
            score += 0.5

        scored_paras.append((idx, score))

    # Sort paragraphs by score descending
    scored_paras.sort(key=lambda x: x[1], reverse=True)

    # Select top N paragraph indices
    top_indices = [idx for idx, _ in scored_paras[:top_n_paragraphs]]

    # Expand window by ±1 neighboring paragraph
    selected_indices: Set[int] = set()
    for idx in top_indices:
        for offset in range(-window_expansion, window_expansion + 1):
            neighbor = idx + offset
            if 0 <= neighbor < len(paras):
                selected_indices.add(neighbor)

    # Sort indices in original chronological paragraph order
    sorted_indices = sorted(selected_indices)

    # Join selected paragraphs into coherent snippet
    snippet_paras = [paras[i] for i in sorted_indices]
    return "\n\n".join(snippet_paras)


class ContextBuilder:
    """Intelligent Context Builder layer for extracting snippets & structuring context."""

    def __init__(
        self,
        max_articles: int = MAX_CONTEXT_ARTICLES,
        max_characters: int = MAX_CONTEXT_CHARACTERS,
        enable_snippets: bool = True,
    ):
        """Initialize ContextBuilder.

        Args:
            max_articles: Maximum number of articles to include (default: 5).
            max_characters: Maximum total character length of formatted context (default: 8000).
            enable_snippets: Whether to enable intelligent paragraph snippet extraction (default: True).
        """
        self.max_articles = max_articles
        self.max_characters = max_characters
        self.enable_snippets = enable_snippets

    def build_context(
        self,
        raw_articles: Optional[List[Dict[str, Any]]],
        query: Optional[str] = None,
    ) -> ContextPackage:
        """Process, deduplicate, extract snippets, format, and package retrieved article dicts.

        Args:
            raw_articles: List of raw article dictionaries from retriever.
            query: Optional user query string for query-relevant snippet extraction.

        Returns:
            ContextPackage containing formatted context and token compression metrics.
        """
        if not raw_articles:
            return ContextPackage(
                formatted_context="",
                articles=[],
                sources=[],
                article_count=0,
                original_article_count=0,
                snippet_count=0,
                characters_before=0,
                characters_after=0,
                estimated_tokens_before=0,
                estimated_tokens_after=0,
                compression_ratio=0.0,
                total_characters=0,
                estimated_tokens=0,
                is_truncated=False,
            )

        seen_ids = set()
        deduped_articles: List[ContextArticle] = []
        sources: List[Dict[str, Any]] = []

        chars_before = 0
        total_snippets_extracted = 0

        # 1. Deduplicate by ID & Extract Snippets
        for item in raw_articles:
            if not isinstance(item, dict):
                continue

            art_id = item.get("id")
            if art_id is None or art_id in seen_ids:
                continue

            seen_ids.add(art_id)

            title = (item.get("title") or "").strip()
            content = (item.get("content") or "").strip()

            if not title and not content:
                continue

            chars_before += len(title) + len(content)

            # Apply Intelligent Snippet Extraction if enabled
            if self.enable_snippets and content:
                snippet_text = extract_snippets(content, query=query)
                total_snippets_extracted += 1
            else:
                snippet_text = content

            district = item.get("district") or item.get("district_name")
            category = item.get("category") or item.get("category_name")
            pub_date = item.get("createdAt") or item.get("date") or item.get("published_at")
            url = item.get("url") or item.get("link")

            ctx_art = ContextArticle(
                id=int(art_id),
                title=title,
                content=snippet_text,
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

            lines.append(f"Relevant Snippet:\n{art.content}")

            block_text = "\n".join(lines)
            needed_len = len(block_text) + (2 if parts else 0)

            if current_length + needed_len > self.max_characters:
                rem_chars = self.max_characters - current_length - (2 if parts else 0)
                if rem_chars > 200:
                    truncated_content = art.content[: rem_chars - 100] + " ... [Truncated]"
                    lines[-1] = f"Relevant Snippet:\n{truncated_content}"
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
        chars_after = len(formatted_str)

        estimated_tokens_before = int(chars_before / APPROX_CHARS_PER_TOKEN)
        estimated_tokens_after = int(chars_after / APPROX_CHARS_PER_TOKEN)

        compression_ratio = 0.0
        if chars_before > chars_after:
            compression_ratio = round((1.0 - (chars_after / max(1, chars_before))) * 100.0, 1)

        logger.info(
            "Built Intelligent ContextPackage: articles=%d/%d, chars_before=%d, chars_after=%d, "
            "tokens_before=%d, tokens_after=%d, compression=%.1f%%, truncated=%s",
            len(included_articles),
            len(raw_articles),
            chars_before,
            chars_after,
            estimated_tokens_before,
            estimated_tokens_after,
            compression_ratio,
            is_truncated,
        )

        return ContextPackage(
            formatted_context=formatted_str,
            articles=included_articles,
            sources=included_sources,
            article_count=len(included_articles),
            original_article_count=len(raw_articles),
            snippet_count=total_snippets_extracted,
            characters_before=chars_before,
            characters_after=chars_after,
            estimated_tokens_before=estimated_tokens_before,
            estimated_tokens_after=estimated_tokens_after,
            compression_ratio=compression_ratio,
            total_characters=chars_after,
            estimated_tokens=estimated_tokens_after,
            is_truncated=is_truncated,
        )
