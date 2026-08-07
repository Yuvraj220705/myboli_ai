"""Sprint 4.0.0 Refactored: Dynamic Unknown Entity Guardrail for Maayboli AI.

Provides scalable, config-driven detection of unsupported foreign entities, companies, products,
and out-of-scope proper nouns to prevent keyword over-matching in MySQL retrieval.
"""

from dataclasses import dataclass, field
import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from entity_normalizer import DistrictNormalizer, PersonNormalizer, WordNormalizer

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
FOREIGN_ENTITIES_PATH = CONFIG_DIR / "foreign_entities.json"
SUPPORTING_TERMS_PATH = CONFIG_DIR / "supporting_terms.json"

__all__ = [
    "UnknownEntityResult",
    "UnknownEntityGuard",
]


@dataclass
class UnknownEntityResult:
    """Structured result produced by UnknownEntityGuard inspection.

    Attributes:
        unknown_entities: List of tokens/entities unrecognized in local corpus scope.
        known_entities: List of recognized Maharashtra districts, leaders, or words.
        critical_entities: Sub-list of primary subject entities driving user query intent.
        supporting_terms: Supporting generic nouns, verbs, or location context terms.
        unknown_entity_ratio: Ratio of unknown critical entities to total subject tokens.
        should_block: Boolean flag indicating if retrieval should be safely blocked.
        reason: Explanation string for audit and logging purposes.
        confidence: Confidence level of decision ("HIGH", "MEDIUM", "LOW").
    """
    unknown_entities: List[str] = field(default_factory=list)
    known_entities: List[str] = field(default_factory=list)
    critical_entities: List[str] = field(default_factory=list)
    supporting_terms: List[str] = field(default_factory=list)
    unknown_entity_ratio: float = 0.0
    should_block: bool = False
    reason: str = "No critical entity issues detected."
    confidence: str = "HIGH"


def load_supporting_terms(config_path: Path = SUPPORTING_TERMS_PATH) -> Set[str]:
    """Load generic supporting terms set from JSON configuration file."""
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                terms = data.get("supporting_terms", [])
                logger.info("Loaded %d supporting terms from %s", len(terms), config_path.name)
                return set(terms)
        except Exception as e:
            logger.error("Failed to load supporting terms from %s: %s", config_path, e)

    # Hardcoded fallback set if config file is missing
    return {
        "अध्यक्ष", "प्रदेशाध्यक्ष", "पंतप्रधान", "मुख्यमंत्री", "मंत्री", "खासदार", "आमदार", "नेते", "अधिकारी", "पोलिस", "पोलीस",
        "दौरा", "भाषण", "सभेत", "सभा", "बैठक", "बैठकीत", "निर्णय", "घोषणा", "विधान", "अपघात", "पाऊस", "हवामान", "वेळापत्रक",
        "निकालाची", "निकाल", "आरक्षण", "कर्जमाफी", "निवडणूक", "भरती", "आंदोलन", "कुंभमेळा", "सामना", "लिलाव", "खेळाडू",
        "महाराष्ट्र", "महाराष्ट्रातील", "महाराष्ट्रात", "भारत", "भारतात", "भारतातील", "जिल्हा", "जिल्ह्यात", "शहर", "शहरातील",
        "सांगा", "माहिती", "बातमी", "बातम्या", "अपडेट", "काय", "आहे", "नाही", "कधी", "कसे", "कोण", "कशा", "आज", "काल", "आजची",
        "नवीन", "ताजी", "ताज्या", "विशेष", "सविस्तर", "मला", "त्याबद्दल", "घेऊन", "येणार", "झालं", "झाली", "केले", "होते",
        "विषयी", "संबंधी", "बद्दल", "उत्तर", "प्रश्न", "दर", "किंमत", "घसरण", "वाढ",
    }


def load_foreign_entity_patterns(config_path: Path = FOREIGN_ENTITIES_PATH) -> List[Tuple[str, re.Pattern]]:
    """Load foreign entity regular expression patterns from JSON configuration file."""
    compiled_patterns: List[Tuple[str, re.Pattern]] = []

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for category, entity_list in data.items():
                    if isinstance(entity_list, list):
                        for entity in entity_list:
                            name = entity.get("name", "Unknown Entity")
                            patterns = entity.get("patterns", [])
                            for pat_str in patterns:
                                try:
                                    compiled_patterns.append((name, re.compile(rf"\b{pat_str}\b", re.IGNORECASE)))
                                except re.error as reg_err:
                                    logger.error("Invalid regex pattern '%s' for %s: %s", pat_str, name, reg_err)
                logger.info("Compiled %d foreign entity patterns from %s", len(compiled_patterns), config_path.name)
                return compiled_patterns
        except Exception as e:
            logger.error("Failed to load foreign entity patterns from %s: %s", config_path, e)

    # Fallback default patterns if config file is missing
    fallback_raw = [
        ("Joe Biden", r"(जो|ज्यो|अध्यक्ष)?\s*(बायडेन|बायडन|biden)"),
        ("Donald Trump", r"(डोनाल्ड)?\s*(ट्रम्प|trump)"),
        ("Cristiano Ronaldo", r"(क्रिस्टियानो)?\s*(रोनाल्डो|ronaldo)"),
        ("Elon Musk", r"(इलॉन|एलोन)?\s*(मस्क|musk)"),
        ("Tesla", r"(टेस्ला|tesla)"),
        ("OpenAI", r"(ओपनएआय|openai|chatgpt)"),
        ("Bitcoin", r"(बिटकॉइन|बिटकॉईन|bitcoin|crypto)"),
    ]
    return [(name, re.compile(rf"\b{pat}\b", re.IGNORECASE)) for name, pat in fallback_raw]


class UnknownEntityGuard:
    """Config-driven, deterministic guardrail component that inspects user queries for unsupported entities."""

    def __init__(
        self,
        district_normalizer: Optional[DistrictNormalizer] = None,
        person_normalizer: Optional[PersonNormalizer] = None,
        word_normalizer: Optional[WordNormalizer] = None,
        foreign_config_path: Path = FOREIGN_ENTITIES_PATH,
        supporting_config_path: Path = SUPPORTING_TERMS_PATH,
    ):
        """Initialize UnknownEntityGuard with dynamic JSON configuration loading."""
        self.district_normalizer = district_normalizer or DistrictNormalizer()
        self.person_normalizer = person_normalizer or PersonNormalizer()
        self.word_normalizer = word_normalizer or WordNormalizer()

        # Dynamic Config Loading
        self.foreign_patterns = load_foreign_entity_patterns(foreign_config_path)
        self.supporting_terms_set = load_supporting_terms(supporting_config_path)

    def inspect_query(self, query: str, query_info: Optional[Any] = None) -> UnknownEntityResult:
        """Inspect query to identify ALL known vs unknown critical entities and determine blocking.

        Args:
            query: Input user query string.
            query_info: Optional QueryInfo object if already generated.

        Returns:
            UnknownEntityResult: Structured inspection output.
        """
        if not query or not query.strip():
            return UnknownEntityResult(should_block=False, reason="Empty query")

        clean_q = query.strip()
        tokens = [t for t in re.split(r"[\s,\.\?\!]+", clean_q) if t]

        known_entities: List[str] = []
        unknown_entities: List[str] = []
        critical_entities: List[str] = []
        supporting_terms: List[str] = []

        # Step 1: Check against existing District, Person, and Word Normalizers
        dist_res = self.district_normalizer.normalize_query(clean_q)
        if dist_res and hasattr(dist_res, "matched_districts") and dist_res.matched_districts:
            known_entities.append(f"District: {dist_res.matched_districts[0].canonical_name}")

        person_res = self.person_normalizer.normalize_query(clean_q)
        if person_res and hasattr(person_res, "matched_people") and person_res.matched_people:
            known_entities.append(f"Person: {person_res.matched_people[0].canonical_name}")

        # Step 2: Check ALL Foreign / Out-of-Scope Critical Patterns (Multi-entity detection - NO BREAK!)
        foreign_matches: List[str] = []
        for entity_label, pattern in self.foreign_patterns:
            match = pattern.search(clean_q)
            if match:
                matched_text = match.group(0).strip()
                entity_desc = f"{entity_label} ('{matched_text}')"
                if matched_text not in critical_entities and entity_label not in foreign_matches:
                    foreign_matches.append(entity_label)
                    critical_entities.append(matched_text)
                    unknown_entities.append(matched_text)

        # Step 3: Classify remaining tokens into Supporting Terms vs Unknown Tokens
        for token in tokens:
            token_clean = token.strip()
            if not token_clean:
                continue

            # Check if token is in supporting terms set
            if token_clean in self.supporting_terms_set or any(sup in token_clean for sup in ["बातमी", "पाऊस", "सभा", "दौरा", "अपघात"]):
                supporting_terms.append(token_clean)
                continue

            # Check English unrecognized words
            if re.match(r"^[a-zA-Z0-9]+$", token_clean):
                if token_clean.lower() in {"pune", "sindhudurg", "kolhapur", "ratnagiri", "mumbai", "nagpur", "rain", "politics", "news", "status", "update", "visit", "speech"}:
                    known_entities.append(token_clean)
                else:
                    if token_clean not in critical_entities:
                        critical_entities.append(token_clean)
                        unknown_entities.append(token_clean)

        # Helper to preserve list order while removing duplicates
        def _unique_list(seq: List[str]) -> List[str]:
            seen = set()
            return [x for x in seq if not (x in seen or seen.add(x))]

        clean_critical = _unique_list(critical_entities)
        clean_unknown = _unique_list(unknown_entities)
        clean_known = _unique_list(known_entities)
        clean_supporting = _unique_list(supporting_terms)

        # Step 4: Decision Logic
        if len(foreign_matches) > 0 or (len(clean_critical) > 0 and len(clean_known) == 0):
            primary_entities_str = ", ".join(clean_critical)
            reason = f"Unsupported critical entity(ies) detected: [{primary_entities_str}]. Query is out of Maharashtra regional news scope."
            logger.info("BLOCKED by UnknownEntityGuard: query='%s' reason='%s'", clean_q[:50], reason)
            return UnknownEntityResult(
                unknown_entities=clean_unknown,
                known_entities=clean_known,
                critical_entities=clean_critical,
                supporting_terms=clean_supporting,
                unknown_entity_ratio=1.0 if clean_critical else 0.0,
                should_block=True,
                reason=reason,
                confidence="HIGH",
            )

        logger.debug("PASSED UnknownEntityGuard: query='%s' known=%s", clean_q[:50], clean_known)
        return UnknownEntityResult(
            unknown_entities=clean_unknown,
            known_entities=clean_known,
            critical_entities=clean_critical,
            supporting_terms=clean_supporting,
            unknown_entity_ratio=0.0,
            should_block=False,
            reason="All critical entities are supported within Maharashtra regional scope.",
            confidence="HIGH",
        )
