"""Entity Normalization and Devanagari Query Processing Module.

Provides tokenization, NFC Unicode normalization, Devanagari grammatical suffix stripping,
pluggable matching strategies (RapidFuzz / Exact), and entity-type isolated normalization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
import logging
import re
from typing import Dict, List, Optional, Set, Tuple
import unicodedata

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

__all__ = [
    "EntityType",
    "MatchedEntity",
    "EntityCorrection",
    "QueryNormalizationResult",
    "EntityMatchingStrategy",
    "RapidFuzzMatchingStrategy",
    "ExactMatchingStrategy",
    "EntityRegistry",
    "EntityNormalizer",
    "normalize_unicode",
    "strip_devanagari_suffix",
    "tokenize_query",
]


# ======================================================
# 1. Enums and Data Models
# ======================================================

class EntityType(Enum):
    """Supported entity categories for isolated matching."""
    DISTRICT = "district"
    CATEGORY = "category"
    PERSON = "person"
    ORGANIZATION = "organization"
    VILLAGE = "village"
    POLITICAL_PARTY = "political_party"
    OTHER = "other"


@dataclass(frozen=True)
class MatchedEntity:
    """Represents a successfully recognized canonical entity in the query.

    Attributes:
        entity_type: Category of the entity (e.g. DISTRICT, CATEGORY, PERSON).
        original_value: The raw input token or text segment from the user.
        canonical_value: The standardized DB / system name of the entity.
        confidence: Match confidence score normalized between 0.0 and 100.0.
    """
    entity_type: EntityType
    original_value: str
    canonical_value: str
    confidence: float


@dataclass(frozen=True)
class EntityCorrection:
    """Represents a query token modification or spelling correction performed.

    Attributes:
        original_token: Raw token prior to processing.
        stripped_token: Token after Devanagari suffix removal.
        canonical_value: Canonical target string substituted.
        confidence: Confidence score of the correction match (0.0 - 100.0).
    """
    original_token: str
    stripped_token: str
    canonical_value: str
    confidence: float


@dataclass
class QueryNormalizationResult:
    """Complete result object returned after query normalization.

    Attributes:
        original_query: Raw user input question.
        normalized_query: Cleaned query string with corrected canonical terms.
        matched_entities: List of all matched entities grouped by type.
        corrections: List of token corrections performed during normalization.
        unmatched_tokens: Tokens that did not match any entity provider.
    """
    original_query: str
    normalized_query: str
    matched_entities: List[MatchedEntity] = field(default_factory=list)
    corrections: List[EntityCorrection] = field(default_factory=list)
    unmatched_tokens: List[str] = field(default_factory=list)


# ======================================================
# 2. Text Processing Helpers
# ======================================================

def normalize_unicode(text: str) -> str:
    """Perform standard NFC Unicode normalization on input string.

    Args:
        text: Input Devanagari or English text.

    Returns:
        Canonical NFC normalized string.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.strip())


# Ordered Devanagari grammatical suffixes for Marathi (longest suffix first to prevent partial matches)
_DEVANAGARI_SUFFIX_PATTERNS: List[str] = [
    "मध्येच",
    "मध्ये",
    "ातील",
    "तील",
    "ातील",
    "ातून",
    "ात",
    "च्या",
    "साठी",
    "कडून",
    "वरून",
    "पर्यंत",
    "बद्दल",
    "जवळ",
    "तील",
    "ने",
    "वर",
    "चा",
    "ची",
    "चे",
    "ात",
    "त",
]

# Regex pattern for suffix stripping anchored at end of token
_SUFFIX_REGEX = re.compile(rf"(?:{'|'.join(re.escape(s) for s in _DEVANAGARI_SUFFIX_PATTERNS)})$", flags=re.UNICODE)


def strip_devanagari_suffix(token: str, min_stem_length: int = 3) -> str:
    """Strip common Marathi grammatical location & possessive suffixes from a token.

    Preserves meaningful root stems by enforcing a minimum stem length constraint.

    Args:
        token: Single Devanagari word token.
        min_stem_length: Minimum character length of the root stem to retain.

    Returns:
        Stemmed token with grammatical suffix removed.
    """
    if not token or len(token) <= min_stem_length:
        return token

    cleaned = token.strip()
    match = _SUFFIX_REGEX.search(cleaned)

    if match:
        suffix = match.group(0)
        stem = cleaned[:-len(suffix)]
        if len(stem) >= min_stem_length:
            return stem

    return cleaned


def tokenize_query(query: str) -> List[str]:
    """Tokenize query string into non-empty word tokens.

    Args:
        query: Raw or normalized query string.

    Returns:
        List of non-whitespace tokens.
    """
    if not query:
        return []
    # Split by whitespace and common punctuation, preserving Devanagari characters
    tokens = re.split(r"[\s,?!;:\".'()]+", query)
    return [t for t in tokens if t]


# ======================================================
# 3. Strategy Pattern for Entity Matching
# ======================================================

class EntityMatchingStrategy(ABC):
    """Abstract Strategy interface for token entity matching."""

    @abstractmethod
    def match(
        self,
        token: str,
        candidates: Dict[str, str],
        min_threshold: float = 70.0,
    ) -> Optional[Tuple[str, float]]:
        """Match a token against candidate entity dictionary.

        Args:
            token: The candidate word token (or stripped token).
            candidates: Mapping of candidate surface string -> Canonical Entity string.
            min_threshold: Minimum acceptable score threshold (0 - 100).

        Returns:
            Tuple of (Canonical Entity Name, Confidence Score) if matched, else None.
        """
        pass


class RapidFuzzMatchingStrategy(EntityMatchingStrategy):
    """RapidFuzz implementation of fuzzy matching strategy using Sequence Ratio."""

    def __init__(self, score_cutoff: float = 70.0):
        self.score_cutoff = score_cutoff

    def match(
        self,
        token: str,
        candidates: Dict[str, str],
        min_threshold: float = 70.0,
    ) -> Optional[Tuple[str, float]]:
        if not token or not candidates:
            return None

        threshold = max(min_threshold, self.score_cutoff)
        choices = list(candidates.keys())

        # Extract best fuzzy match using RapidFuzz ratio (prevents partial substring false matches on multi-word strings)
        best_match = process.extractOne(
            token,
            choices,
            scorer=fuzz.ratio,
            score_cutoff=threshold,
        )

        if best_match:
            matched_surface_form, score, _ = best_match
            canonical = candidates[matched_surface_form]
            return canonical, float(score)

        return None


class ExactMatchingStrategy(EntityMatchingStrategy):
    """Exact string equality matching strategy."""

    def match(
        self,
        token: str,
        candidates: Dict[str, str],
        min_threshold: float = 80.0,
    ) -> Optional[Tuple[str, float]]:
        if not token or not candidates:
            return None

        # Direct exact or case-insensitive match
        for surface_form, canonical in candidates.items():
            if token.lower() == surface_form.lower():
                return canonical, 100.0

        return None


# ======================================================
# 4. Injectable Entity Registry Provider
# ======================================================

class EntityRegistry:
    """Registry holding injectable entity datasets segregated by EntityType."""

    def __init__(self):
        # Dict[EntityType, Dict[surface_form, canonical_name]]
        self._registry: Dict[EntityType, Dict[str, str]] = {
            entity_type: {} for entity_type in EntityType
        }

    def register_entity(self, entity_type: EntityType, surface_form: str, canonical_name: str) -> None:
        """Register a single entity surface form and its canonical target.

        Args:
            entity_type: Type enum (DISTRICT, CATEGORY, PERSON, etc.)
            surface_form: Recognized surface text or alias (e.g. "कोल्हापूर", "कोलापुर")
            canonical_name: Canonical DB / system name (e.g. "Kolhapur", "Politics")
        """
        norm_surface = normalize_unicode(surface_form)
        self._registry[entity_type][norm_surface] = canonical_name

    def register_bulk(
        self,
        entity_type: EntityType,
        mapping: Dict[str, List[str]],
    ) -> None:
        """Bulk register canonical names and their alias lists.

        Args:
            entity_type: Type enum.
            mapping: Dict mapping canonical_name -> list of surface aliases.
        """
        for canonical_name, aliases in mapping.items():
            # Register canonical name itself
            self.register_entity(entity_type, canonical_name, canonical_name)
            for alias in aliases:
                self.register_entity(entity_type, alias, canonical_name)

    def get_candidates(self, entity_type: EntityType) -> Dict[str, str]:
        """Get candidate surface forms for a specific entity type.

        Args:
            entity_type: Target EntityType enum.

        Returns:
            Dict mapping surface form -> canonical name.
        """
        return self._registry.get(entity_type, {})


# ======================================================
# 5. Default Built-in Entity Provider Defaults
# ======================================================

def create_default_registry() -> EntityRegistry:
    """Create a baseline registry pre-populated with standard Marathi entities.

    Returns:
        Configured EntityRegistry instance.
    """
    registry = EntityRegistry()

    # Register standard Maharashtra Districts
    districts = {
        "Sindhudurg": ["सिंधुदुर्ग", "सिधुदुर्ग", "सिंदुदुर्ग", "सिंधुदुर्गात"],
        "Kolhapur": ["कोल्हापूर", "कोलापुर", "कोल्हापुरात"],
        "Ratnagiri": ["रत्नागिरी", "रत्नागीरी", "रत्नागिरीत"],
        "Mumbai": ["मुंबई", "मुंबइ", "मुंबईत", "मुंबईमध्ये"],
        "Pune": ["पुणे", "पुण्यात", "पुण्यामध्ये"],
        "Sangli": ["सांगली", "सांगलीत"],
        "Satara": ["सातारा", "साताऱ्यात"],
        "Nashik": ["नाशिक", "नाशिकमध्ये"],
        "Nagpur": ["नागपूर", "नागपुर"],
    }
    registry.register_bulk(EntityType.DISTRICT, districts)

    # Register Categories
    categories = {
        "Politics": ["राजकारण", "राजकीय", "राजकरण"],
        "Sports": ["क्रीडा", "खेळ"],
        "Entertainment": ["मनोरंजन", "चित्रपट", "बॉलीवूड"],
        "Crime": ["गुन्हे", "क्राइम", "अपघात"],
        "Education": ["शिक्षण"],
        "Health": ["आरोग्य"],
    }
    registry.register_bulk(EntityType.CATEGORY, categories)

    # Register Key Political / Public Figures
    persons = {
        "Amit Shah": ["अमित शाह", "अमीत शाह"],
        "Devendra Fadnavis": ["देवेंद्र फडणवीस", "फडणवीस"],
        "Uddhav Thackeray": ["उद्धव ठाकरे", "उद्वव ठाकरे", "उध्दव ठाकरे"],
        "Ajit Pawar": ["अजित पवार", "अजीत पवार"],
        "Vinayak Raut": ["विनायक राऊत", "विनायक राउत"],
    }
    registry.register_bulk(EntityType.PERSON, persons)

    return registry


# ======================================================
# 6. Core Orchestrator: EntityNormalizer
# ======================================================

class EntityNormalizer:
    """Independent Entity Normalization Service.

    Responsible for Unicode normalization, tokenization, Devanagari suffix stripping,
    and type-isolated entity resolution using an injectable matching strategy.
    """

    def __init__(
        self,
        registry: Optional[EntityRegistry] = None,
        matching_strategy: Optional[EntityMatchingStrategy] = None,
        min_confidence_threshold: float = 70.0,
    ):
        """Initialize EntityNormalizer.

        Args:
            registry: Injectable EntityRegistry instance. Uses baseline defaults if None.
            matching_strategy: Strategy implementation for string matching. Defaults to RapidFuzz.
            min_confidence_threshold: Minimum match confidence score (0 - 100).
        """
        self.registry = registry or create_default_registry()
        self.matching_strategy = matching_strategy or RapidFuzzMatchingStrategy(score_cutoff=min_confidence_threshold)
        self.min_confidence_threshold = min_confidence_threshold

    def normalize_query(self, query: str) -> QueryNormalizationResult:
        """Normalize a raw query string into canonical entity resolution object.

        Args:
            query: Raw user query question.

        Returns:
            QueryNormalizationResult object containing normalized query and details.
        """
        if not query or not query.strip():
            return QueryNormalizationResult(original_query="", normalized_query="")

        # Step 1: Unicode Normalization
        norm_raw = normalize_unicode(query)

        # Step 2: Tokenization
        tokens = tokenize_query(norm_raw)

        matched_entities: List[MatchedEntity] = []
        corrections: List[EntityCorrection] = []
        unmatched_tokens: List[str] = []
        replaced_tokens: List[str] = list(tokens)

        # Track which tokens have already been processed to avoid re-matching multi-word tokens
        processed_indices: Set[int] = set()

        for idx, token in enumerate(tokens):
            if idx in processed_indices:
                continue

            # Step 3: Devanagari Suffix Stripping
            stripped_token = strip_devanagari_suffix(token)

            token_matched = False

            # Step 4: Type-Isolated Entity Matching
            # Iterate through configured entity types separately
            for entity_type in EntityType:
                candidates = self.registry.get_candidates(entity_type)
                if not candidates:
                    continue

                # First try matching two-word tokens (e.g. "अमित शाह") if adjacent token exists
                if idx + 1 < len(tokens) and (idx + 1) not in processed_indices:
                    two_word_token = f"{token} {tokens[idx + 1]}"
                    match_res = self.matching_strategy.match(
                        two_word_token,
                        candidates,
                        min_threshold=self.min_confidence_threshold,
                    )
                    if match_res:
                        canonical_val, confidence = match_res
                        matched_entities.append(
                            MatchedEntity(
                                entity_type=entity_type,
                                original_value=two_word_token,
                                canonical_value=canonical_val,
                                confidence=confidence,
                            )
                        )
                        corrections.append(
                            EntityCorrection(
                                original_token=two_word_token,
                                stripped_token=two_word_token,
                                canonical_value=canonical_val,
                                confidence=confidence,
                            )
                        )
                        logger.info(
                            "Matched %s entity: '%s' -> '%s' (Confidence: %.1f)",
                            entity_type.value,
                            two_word_token,
                            canonical_val,
                            confidence,
                        )
                        replaced_tokens[idx] = canonical_val
                        replaced_tokens[idx + 1] = ""
                        processed_indices.add(idx)
                        processed_indices.add(idx + 1)
                        token_matched = True
                        break

                # Single-token match (try stripped_token first, then original token)
                for candidate_token in [stripped_token, token]:
                    match_res = self.matching_strategy.match(
                        candidate_token,
                        candidates,
                        min_threshold=self.min_confidence_threshold,
                    )
                    if match_res:
                        canonical_val, confidence = match_res
                        matched_entities.append(
                            MatchedEntity(
                                entity_type=entity_type,
                                original_value=token,
                                canonical_value=canonical_val,
                                confidence=confidence,
                            )
                        )
                        if candidate_token != canonical_val:
                            corrections.append(
                                EntityCorrection(
                                    original_token=token,
                                    stripped_token=stripped_token,
                                    canonical_value=canonical_val,
                                    confidence=confidence,
                                )
                            )
                            logger.info(
                                "Corrected %s token: '%s' (stripped: '%s') -> '%s' (Confidence: %.1f)",
                                entity_type.value,
                                token,
                                stripped_token,
                                canonical_val,
                                confidence,
                            )

                        replaced_tokens[idx] = canonical_val
                        processed_indices.add(idx)
                        token_matched = True
                        break

                if token_matched:
                    break

            if not token_matched:
                unmatched_tokens.append(token)

        # Assemble normalized query text
        normalized_query_text = " ".join([t for t in replaced_tokens if t])

        return QueryNormalizationResult(
            original_query=query,
            normalized_query=normalized_query_text,
            matched_entities=matched_entities,
            corrections=corrections,
            unmatched_tokens=unmatched_tokens,
        )
