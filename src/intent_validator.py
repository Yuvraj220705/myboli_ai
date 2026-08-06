"""Sprint 2.1: Intent Validation Layer for Maayboli AI.

Acts as a strict Quality Gate between Context Engineering and Gemini Answer Generation.
Deterministically evaluates how well the generated ContextPackage satisfies the user's
original QueryInfo intent without modifying articles, rewriting queries, or calling LLMs.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Set

from entity_normalizer import PersonNormalizer, normalize_unicode
from query_processor import QueryInfo, CATEGORY_ALIASES, DISTRICTS

logger = logging.getLogger(__name__)

# Configurable Weights (Summing to 100.0)
WEIGHT_DISTRICT: float = 25.0
WEIGHT_PERSON: float = 25.0
WEIGHT_CATEGORY: float = 30.0
WEIGHT_DATE: float = 20.0

# Confidence Thresholds
CONFIDENCE_HIGH_THRESHOLD: float = 80.0
CONFIDENCE_MEDIUM_THRESHOLD: float = 50.0

# Retrieval Status Thresholds
STATUS_EXACT_THRESHOLD: float = 90.0
STATUS_PARTIAL_THRESHOLD: float = 60.0
STATUS_RELATED_THRESHOLD: float = 30.0

# Shared PersonNormalizer singleton for entity extraction
_PERSON_NORMALIZER = PersonNormalizer()

# Reverse mapping of English district names to Devanagari names
_DISTRICT_ENG_TO_MAR: Dict[str, str] = {v: k for k, v in DISTRICTS.items()}

__all__ = [
    "IntentValidationResult",
    "IntentValidator",
    "WEIGHT_DISTRICT",
    "WEIGHT_PERSON",
    "WEIGHT_CATEGORY",
    "WEIGHT_DATE",
]


@dataclass
class IntentValidationResult:
    """Structured quality evaluation of retrieved context against user intent.

    Attributes:
        overall_match_score: Overall percentage score (0.0 to 100.0).
        confidence: Confidence level ("HIGH", "MEDIUM", "LOW").
        retrieval_status: Status ("EXACT_MATCH", "PARTIAL_MATCH", "RELATED_MATCH", "NO_MATCH").
        validation_reason: Human-readable explanation of intent satisfaction.
        district_match: Flag indicating if target district was matched.
        person_match: Flag indicating if target person entity was matched.
        category_match: Flag indicating if target category/topic was matched.
        date_match: Flag indicating if target date was matched.
        matched_entities: List of matched entity strings.
        missing_entities: List of missing entity strings.
        matched_topics: List of matched topic/keyword strings.
        missing_topics: List of missing topic/keyword strings.
    """
    overall_match_score: float
    confidence: str
    retrieval_status: str
    validation_reason: str
    district_match: bool
    person_match: bool
    category_match: bool
    date_match: bool
    matched_entities: List[str] = field(default_factory=list)
    missing_entities: List[str] = field(default_factory=list)
    matched_topics: List[str] = field(default_factory=list)
    missing_topics: List[str] = field(default_factory=list)


class IntentValidator:
    """Deterministic Quality Gate evaluating context satisfaction of query intent."""

    def __init__(
        self,
        weight_district: float = WEIGHT_DISTRICT,
        weight_person: float = WEIGHT_PERSON,
        weight_category: float = WEIGHT_CATEGORY,
        weight_date: float = WEIGHT_DATE,
    ):
        """Initialize IntentValidator with configurable component weights.

        Args:
            weight_district: Weight for district match (default: 25.0).
            weight_person: Weight for person entity match (default: 25.0).
            weight_category: Weight for category/topic match (default: 30.0).
            weight_date: Weight for date match (default: 20.0).
        """
        self.weight_district = weight_district
        self.weight_person = weight_person
        self.weight_category = weight_category
        self.weight_date = weight_date

    def validate(
        self,
        query_info: QueryInfo,
        context_pkg: Any,
    ) -> IntentValidationResult:
        """Evaluate how well context_pkg satisfies query_info intent.

        Args:
            query_info: QueryInfo object from query_processor.
            context_pkg: ContextPackage object from context_builder.

        Returns:
            IntentValidationResult detailing quality scores and status.
        """
        if not context_pkg or not hasattr(context_pkg, "articles") or not context_pkg.articles:
            return IntentValidationResult(
                overall_match_score=0.0,
                confidence="LOW",
                retrieval_status="NO_MATCH",
                validation_reason="No matching published articles retrieved in context.",
                district_match=False,
                person_match=False,
                category_match=False,
                date_match=False,
                matched_entities=[],
                missing_entities=[],
                matched_topics=[],
                missing_topics=[],
            )

        # Aggregate context text across snippets and metadata
        context_text_norm = normalize_unicode(context_pkg.formatted_context.lower())
        articles = context_pkg.articles

        matched_entities: List[str] = []
        missing_entities: List[str] = []
        matched_topics: List[str] = []
        missing_topics: List[str] = []

        criteria_evaluated: Dict[str, bool] = {}
        criteria_weights: Dict[str, float] = {}

        # -------------------------------------------------------------
        # 1. District Matching
        # -------------------------------------------------------------
        if query_info.district:
            target_district_eng = query_info.district
            target_district_mar = _DISTRICT_ENG_TO_MAR.get(target_district_eng, target_district_eng)

            district_found = False
            for art in articles:
                if art.district and art.district.lower() == target_district_eng.lower():
                    district_found = True
                    break
                if target_district_mar and normalize_unicode(target_district_mar.lower()) in context_text_norm:
                    district_found = True
                    break

            criteria_evaluated["district"] = district_found
            criteria_weights["district"] = self.weight_district

            if district_found:
                matched_entities.append(f"District: {target_district_eng}")
            else:
                missing_entities.append(f"District: {target_district_eng}")

        # -------------------------------------------------------------
        # 2. Person Entity Matching
        # -------------------------------------------------------------
        person_match_res = _PERSON_NORMALIZER.normalize_query(query_info.original_query)
        target_person: Optional[str] = None
        if person_match_res and person_match_res.matched_people:
            target_person = person_match_res.matched_people[0].canonical_name

        if target_person:
            target_person_norm = normalize_unicode(target_person.lower())
            person_found = False

            # Check full name or surname tokens
            name_tokens = [t for t in re.findall(r"[\w\u0900-\u097F]+", target_person_norm) if len(t) > 2]
            for token in name_tokens:
                if token in context_text_norm:
                    person_found = True
                    break

            criteria_evaluated["person"] = person_found
            criteria_weights["person"] = self.weight_person

            if person_found:
                matched_entities.append(f"Person: {target_person}")
            else:
                missing_entities.append(f"Person: {target_person}")

        # -------------------------------------------------------------
        # 3. Category / Topic Matching
        # -------------------------------------------------------------
        # Extract topic words from clean query
        clean_words = set(re.findall(r"[\w\u0900-\u097F]+", query_info.clean_query.lower()))
        # Remove known person tokens if present
        if target_person:
            person_tokens = set(re.findall(r"[\w\u0900-\u097F]+", target_person.lower()))
            clean_words -= person_tokens

        target_category = query_info.category
        category_found = False

        if target_category or clean_words:
            matched_words = []
            unmatched_words = []

            for word in clean_words:
                norm_w = normalize_unicode(word)
                if len(norm_w) <= 2:
                    continue
                if norm_w in context_text_norm:
                    matched_words.append(word)
                else:
                    unmatched_words.append(word)

            if target_category:
                cat_aliases = CATEGORY_ALIASES.get(target_category, [target_category])
                for alias in cat_aliases:
                    if normalize_unicode(alias.lower()) in context_text_norm:
                        matched_words.append(alias)
                        break

            category_found = len(matched_words) > 0 or (target_category and any(art.category == target_category for art in articles))

            criteria_evaluated["category"] = category_found
            criteria_weights["category"] = self.weight_category

            matched_topics.extend(matched_words)
            missing_topics.extend(unmatched_words)
            if target_category and not category_found:
                missing_topics.append(f"Category: {target_category}")

        # -------------------------------------------------------------
        # 4. Date Matching
        # -------------------------------------------------------------
        if query_info.date:
            target_date_str = str(query_info.date)
            date_found = any(art.date and target_date_str in str(art.date) for art in articles)

            criteria_evaluated["date"] = date_found
            criteria_weights["date"] = self.weight_date

            if date_found:
                matched_entities.append(f"Date: {target_date_str}")
            else:
                missing_entities.append(f"Date: {target_date_str}")

        # -------------------------------------------------------------
        # 5. Dynamic Weighted Score Calculation
        # -------------------------------------------------------------
        total_weight = sum(criteria_weights.values())
        if total_weight == 0:
            # General query with no specific entity/topic restrictions
            overall_score = 100.0 if articles else 0.0
        else:
            weighted_score = sum(criteria_weights[k] for k, v in criteria_evaluated.items() if v)
            overall_score = round((weighted_score / total_weight) * 100.0, 1)

        # -------------------------------------------------------------
        # 6. Confidence & Retrieval Status Assignment
        # -------------------------------------------------------------
        if overall_score >= CONFIDENCE_HIGH_THRESHOLD:
            confidence = "HIGH"
        elif overall_score >= CONFIDENCE_MEDIUM_THRESHOLD:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        if overall_score >= STATUS_EXACT_THRESHOLD:
            retrieval_status = "EXACT_MATCH"
        elif overall_score >= STATUS_PARTIAL_THRESHOLD:
            retrieval_status = "PARTIAL_MATCH"
        elif overall_score >= STATUS_RELATED_THRESHOLD:
            retrieval_status = "RELATED_MATCH"
        else:
            retrieval_status = "NO_MATCH"

        # -------------------------------------------------------------
        # 7. Generate Validation Reason Explanation
        # -------------------------------------------------------------
        reason_parts = []
        if matched_entities:
            reason_parts.append(f"Matched entities: {', '.join(matched_entities)}.")
        if matched_topics:
            reason_parts.append(f"Matched topics: {', '.join(matched_topics)}.")
        if missing_entities:
            reason_parts.append(f"Missing entities: {', '.join(missing_entities)}.")
        if missing_topics:
            reason_parts.append(f"Missing topics: {', '.join(missing_topics)}.")

        if not reason_parts:
            validation_reason = "General news articles retrieved successfully."
        else:
            validation_reason = " ".join(reason_parts)

        logger.info(
            "Intent Validation: score=%.1f, confidence=%s, status=%s, reason='%s'",
            overall_score,
            confidence,
            retrieval_status,
            validation_reason,
        )

        return IntentValidationResult(
            overall_match_score=overall_score,
            confidence=confidence,
            retrieval_status=retrieval_status,
            validation_reason=validation_reason,
            district_match=criteria_evaluated.get("district", False),
            person_match=criteria_evaluated.get("person", False),
            category_match=criteria_evaluated.get("category", False),
            date_match=criteria_evaluated.get("date", False),
            matched_entities=matched_entities,
            missing_entities=missing_entities,
            matched_topics=matched_topics,
            missing_topics=missing_topics,
        )
