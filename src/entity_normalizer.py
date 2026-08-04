"""Sprint 1.2.1: District Normalization Module.

Focused strictly on Devanagari District Name Normalization, NFC Unicode Normalization,
District Suffix Stripping, and RapidFuzz District matching.

Does NOT handle people, categories, common words, or query rewriting.
Completely standalone module with zero external API dependencies.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple
import unicodedata

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)

__all__ = [
    "MatchedDistrict",
    "DistrictNormalizationResult",
    "DistrictNormalizer",
    "MatchedPerson",
    "PersonNormalizationResult",
    "PersonNormalizer",
    "DEFAULT_CANONICAL_PEOPLE",
    "normalize_unicode",
    "strip_district_suffix",
    "tokenize_query",
]


# ======================================================
# 1. Data Models / Dataclasses
# ======================================================

@dataclass(frozen=True)
class MatchedDistrict:
    """Represents a recognized or corrected district entity.

    Attributes:
        canonical_name: Standardized Marathi district name (e.g. "कोल्हापूर").
        original_token: Raw token input from user (e.g. "कोलापुर" or "कोल्हापुरात").
        confidence: Match confidence score normalized between 0.0 and 100.0.
        was_corrected: True if spelling correction or suffix stripping occurred.
    """
    canonical_name: str
    original_token: str
    confidence: float
    was_corrected: bool


@dataclass
class DistrictNormalizationResult:
    """Structured result object returned after district normalization.

    Attributes:
        original_query: Raw user input query string.
        normalized_query: Cleaned query string with canonical district substituted.
        matched_districts: List of matched district objects.
        corrections: Subset of matched_districts where corrections occurred.
        unmatched_tokens: Tokens that were not identified as districts.
    """
    original_query: str
    normalized_query: str
    matched_districts: List[MatchedDistrict] = field(default_factory=list)
    corrections: List[MatchedDistrict] = field(default_factory=list)
    unmatched_tokens: List[str] = field(default_factory=list)


# ======================================================
# 2. Stage 1: Unicode Normalization
# ======================================================

def normalize_unicode(text: str) -> str:
    """Stage 1: Perform standard NFC Unicode normalization on input string.

    Args:
        text: Input string.

    Returns:
        Canonical NFC normalized text string.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text.strip())


# ======================================================
# 3. Stage 2: Tokenization
# ======================================================

def tokenize_query(query: str) -> List[str]:
    """Stage 2: Split query text into clean Devanagari tokens.

    Args:
        query: Normalized query string.

    Returns:
        List of non-whitespace tokens.
    """
    if not query:
        return []
    tokens = re.split(r"[\s,?!;:\".'()]+", query)
    return [t for t in tokens if t]


# ======================================================
# 4. Stage 3: District Suffix Stripping
# ======================================================

# Grammatical location suffixes in Marathi anchored at token end (ordered longest first)
_DISTRICT_SUFFIXES: List[str] = [
    "मध्येच",
    "मध्ये",
    "पासून",
    "ातील",
    "तील",
    "ातून",
    "वरून",
    "पर्यंत",
    "साठी",
    "च्या",
    "ात",
    "ने",
    "वर",
    "चा",
    "ची",
    "चे",
    "ला",
    "त",
]

_SUFFIX_REGEX = re.compile(rf"(?:{'|'.join(re.escape(s) for s in _DISTRICT_SUFFIXES)})$", flags=re.UNICODE)


def strip_district_suffix(token: str, min_stem_length: int = 3) -> str:
    """Stage 3: Remove grammatical location suffixes without damaging root stem.

    Args:
        token: Single Devanagari word token.
        min_stem_length: Minimum stem length required to retain root word.

    Returns:
        Stemmed token with district location suffix stripped.
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


# ======================================================
# 5. Baseline District Dataset (Injectable)
# ======================================================

DEFAULT_MAHARASHTRA_DISTRICTS: Dict[str, List[str]] = {
    "कोल्हापूर": ["कोल्हापूर", "कोलापुर", "कोलहापूर", "कोलापूर", "कोल्हपुर"],
    "नागपूर": ["नागपूर", "नागपुर", "नागपुरा", "नागपुुर"],
    "पुणे": ["पुणे", "पुने", "पूणे", "पुण", "पुण्या"],
    "सिंधुदुर्ग": ["सिंधुदुर्ग", "सिंदुदुर्ग", "सिधुदुर्ग", "सिध्दुदुर्ग", "सिंधुदूर्ग"],
    "रत्नागिरी": ["रत्नागिरी", "रत्नागीरी"],
    "मुंबई": ["मुंबई", "मुंबइ"],
    "सांगली": ["सांगली"],
    "सातारा": ["सातारा", "साताऱ्या"],
    "नाशिक": ["नाशिक"],
    "अहमदनगर": ["अहमदनगर", "नगर"],
    "छत्रपती संभाजीनगर": ["छत्रपती संभाजीनगर", "संभाजीनगर", "औरंगाबाद"],
    "सोलापूर": ["सोलापूर", "सोलापुर"],
    "ठाणे": ["ठाणे", "थाणे"],
    "पालघर": ["पालघर"],
    "रायगड": ["रायगड"],
    "जळगाव": ["जळगाव", "जळगाव"],
    "धुळे": ["धुळे"],
    "नंदुरबार": ["नंदुरबार"],
    "जालना": ["जालना"],
    "बीड": ["बीड"],
    "लातूर": ["लातूर", "लातुर"],
    "धाराशिव": ["धाराशिव", "उस्मानाबाद"],
    "नांदेड": ["नांदेड"],
    "परभणी": ["परभणी"],
    "हिंगोली": ["हिंगोली"],
    "अमरावती": ["अमरावती"],
    "अकोला": ["अकोला"],
    "वाशीम": ["वाशीम"],
    "बुलढाणा": ["बुलढाणा"],
    "यवतमाळ": ["यवतमाळ"],
    "वर्धा": ["वर्धा"],
    "भंडारा": ["भंडारा"],
    "गोंदिया": ["गोंदिया"],
    "चंद्रपूर": ["चंद्रपूर", "चंद्रपुर"],
    "गडचिरोली": ["गडचिरोली"],
}


# ======================================================
# 6. Core Standalone Class: DistrictNormalizer
# ======================================================

class DistrictNormalizer:
    """Sprint 1.2.1: Standalone District Normalizer.

    Executes Unicode NFC normalization, Tokenization, District Suffix Stripping,
    and RapidFuzz district matching against canonical district datasets.
    """

    def __init__(
        self,
        district_dataset: Optional[Dict[str, List[str]]] = None,
        min_confidence_threshold: float = 70.0,
    ):
        """Initialize DistrictNormalizer.

        Args:
            district_dataset: Dict mapping canonical district -> list of typos/aliases.
            min_confidence_threshold: RapidFuzz match threshold (default 70.0).
        """
        raw_dataset = district_dataset or DEFAULT_MAHARASHTRA_DISTRICTS
        self.min_confidence_threshold = min_confidence_threshold

        # Build surface form lookup mapping: surface_form -> canonical_name
        self.candidates: Dict[str, str] = {}
        for canonical, aliases in raw_dataset.items():
            norm_canonical = normalize_unicode(canonical)
            self.candidates[norm_canonical] = norm_canonical
            for alias in aliases:
                norm_alias = normalize_unicode(alias)
                self.candidates[norm_alias] = norm_canonical

    def normalize_query(self, query: str) -> DistrictNormalizationResult:
        """Process raw query and resolve district entities.

        Args:
            query: User question string.

        Returns:
            DistrictNormalizationResult object.
        """
        if not query or not query.strip():
            return DistrictNormalizationResult(original_query="", normalized_query="")

        # Stage 1: Unicode Normalization
        norm_raw = normalize_unicode(query)

        # Stage 2: Tokenization
        tokens = tokenize_query(norm_raw)

        matched_districts: List[MatchedDistrict] = []
        corrections: List[MatchedDistrict] = []
        unmatched_tokens: List[str] = []
        replaced_tokens: List[str] = list(tokens)

        choices = list(self.candidates.keys())

        for idx, token in enumerate(tokens):
            # Stage 3: District Suffix Stripping
            stripped_token = strip_district_suffix(token)

            match_found = False

            # Stage 4: RapidFuzz District Matching
            for candidate_token in [stripped_token, token]:
                best_match = process.extractOne(
                    candidate_token,
                    choices,
                    scorer=fuzz.ratio,
                    score_cutoff=self.min_confidence_threshold,
                )

                if best_match:
                    matched_surface, score, _ = best_match
                    canonical_name = self.candidates[matched_surface]
                    was_corrected = (token != canonical_name)

                    district_obj = MatchedDistrict(
                        canonical_name=canonical_name,
                        original_token=token,
                        confidence=float(score),
                        was_corrected=was_corrected,
                    )
                    matched_districts.append(district_obj)

                    if was_corrected:
                        corrections.append(district_obj)
                        logger.info(
                            "Corrected District: '%s' (stripped: '%s') -> '%s' (Score: %.1f)",
                            token,
                            stripped_token,
                            canonical_name,
                            score,
                        )

                    replaced_tokens[idx] = canonical_name
                    match_found = True
                    break

            if not match_found:
                unmatched_tokens.append(token)

        normalized_text = " ".join(replaced_tokens)

        return DistrictNormalizationResult(
            original_query=query,
            normalized_query=normalized_text,
            matched_districts=matched_districts,
            corrections=corrections,
            unmatched_tokens=unmatched_tokens,
        )


# ======================================================
# 7. Person Data Models & Baseline Dataset (Injectable)
# ======================================================

@dataclass(frozen=True)
class MatchedPerson:
    """Represents a recognized or corrected person entity.

    Attributes:
        canonical_name: Standardized Marathi full name (e.g. "अमित शाह").
        original_text: Raw input token string matched from user input.
        confidence: Match confidence score normalized between 0.0 and 100.0.
        matched_tokens: List of original query tokens that comprised this match.
        was_corrected: True if spelling correction, joined-token splitting, or surname expansion occurred.
        ambiguity_detected: True if multiple canonical people share the input surname/token.
    """
    canonical_name: str
    original_text: str
    confidence: float
    matched_tokens: List[str] = field(default_factory=list)
    was_corrected: bool = False
    ambiguity_detected: bool = False


@dataclass
class PersonNormalizationResult:
    """Structured result object returned after person normalization.

    Attributes:
        original_query: Raw user input query string.
        normalized_query: Query string with person tokens cleaned/substituted.
        matched_people: List of matched person objects.
        corrections: Subset of matched_people where corrections occurred.
        unmatched_tokens: Tokens that were not identified as person entities.
    """
    original_query: str
    normalized_query: str
    matched_people: List[MatchedPerson] = field(default_factory=list)
    corrections: List[MatchedPerson] = field(default_factory=list)
    unmatched_tokens: List[str] = field(default_factory=list)


DEFAULT_CANONICAL_PEOPLE: List[Dict[str, Any]] = [
    {
        "id": 1,
        "name": "अमित शाह",
        "aliases": ["अमित शाह", "अमीत शाह", "अमीतशाह", "अमितशाह", "अमीत स्हा", "अमितसाह"],
    },
    {
        "id": 2,
        "name": "देवेंद्र फडणवीस",
        "aliases": ["देवेंद्र फडणवीस", "फडणवीस", "फडणविस", "देवेंद्र फडणविस"],
    },
    {
        "id": 3,
        "name": "अजित पवार",
        "aliases": ["अजित पवार", "अजीत पवार", "अजीत पावार", "अजित पावार"],
    },
    {
        "id": 4,
        "name": "विनायक राऊत",
        "aliases": ["विनायक राऊत", "विनायक रावत", "राऊत", "राउत", "रावत"],
    },
    {
        "id": 5,
        "name": "उद्धव ठाकरे",
        "aliases": ["उद्धव ठाकरे", "उधव ठाकरे", "उधव", "ठाकरे"],
    },
]


# ======================================================
# 8. Core Standalone Class: PersonNormalizer
# ======================================================

class PersonNormalizer:
    """Sprint 1.2.2: Standalone Person Entity Normalizer.

    Handles spelling mistakes, joined tokens (e.g. 'अमीतशाह'), surname/partial
    name expansion, and ambiguity detection against injectable canonical people datasets.
    """

    def __init__(
        self,
        people_dataset: Optional[List[Dict[str, Any]]] = None,
        min_confidence_threshold: float = 70.0,
    ):
        """Initialize PersonNormalizer.

        Args:
            people_dataset: List of dicts with 'id', 'name', and optional 'aliases'.
            min_confidence_threshold: RapidFuzz score threshold (default 70.0).
        """
        dataset = people_dataset if people_dataset is not None else DEFAULT_CANONICAL_PEOPLE
        self.min_confidence_threshold = min_confidence_threshold

        self.canonical_people: List[str] = []
        self.surface_to_canonical: Dict[str, str] = {}
        self.surname_index: Dict[str, Set[str]] = {}
        self.firstname_index: Dict[str, Set[str]] = {}

        for entry in dataset:
            canonical = normalize_unicode(entry["name"])
            self.canonical_people.append(canonical)
            self.surface_to_canonical[canonical] = canonical

            parts = canonical.split()
            first_name = parts[0] if parts else canonical
            surname = parts[-1] if len(parts) > 1 else canonical

            self.firstname_index.setdefault(first_name, set()).add(canonical)
            self.surname_index.setdefault(surname, set()).add(canonical)

            aliases = entry.get("aliases", [])
            for alias in aliases:
                norm_alias = normalize_unicode(alias)
                self.surface_to_canonical[norm_alias] = canonical

    def _split_joined_token(self, token: str) -> Optional[Tuple[str, str, float]]:
        """Attempt to split joined person tokens (e.g. 'अमीतशाह' -> 'अमित' + 'शाह')."""
        if len(token) < 5:
            return None

        choices_sur = list(self.surname_index.keys())
        choices_first = list(self.firstname_index.keys())

        for i in range(3, len(token) - 1):
            left = token[:i]
            right = token[i:]

            match_first = process.extractOne(left, choices_first, scorer=fuzz.ratio, score_cutoff=70.0)
            match_sur = process.extractOne(right, choices_sur, scorer=fuzz.ratio, score_cutoff=70.0)

            if match_first and match_sur:
                first_name, score1, _ = match_first
                surname, score2, _ = match_sur
                possible_first = self.firstname_index[first_name]
                possible_sur = self.surname_index[surname]
                common = possible_first.intersection(possible_sur)
                if common:
                    canonical = next(iter(common))
                    avg_score = (score1 + score2) / 2.0
                    return canonical, f"{left} {right}", avg_score

        return None

    def normalize_query(self, query: str) -> PersonNormalizationResult:
        """Process raw query and resolve person entities."""
        if not query or not query.strip():
            return PersonNormalizationResult(original_query="", normalized_query="")

        norm_raw = normalize_unicode(query)
        tokens = tokenize_query(norm_raw)

        if not tokens:
            return PersonNormalizationResult(original_query=query, normalized_query=norm_raw)

        matched_people: List[MatchedPerson] = []
        corrections: List[MatchedPerson] = []
        unmatched_tokens: List[str] = list(tokens)

        surface_choices = list(self.surface_to_canonical.keys())

        i = 0
        while i < len(tokens):
            match_found = False
            if i + 1 < len(tokens):
                bigram = f"{tokens[i]} {tokens[i+1]}"
                best = process.extractOne(bigram, surface_choices, scorer=fuzz.ratio, score_cutoff=self.min_confidence_threshold)
                if best:
                    matched_surface, score, _ = best
                    canonical = self.surface_to_canonical[matched_surface]
                    was_corrected = (bigram != canonical)

                    person_obj = MatchedPerson(
                        canonical_name=canonical,
                        original_text=bigram,
                        confidence=float(score),
                        matched_tokens=[tokens[i], tokens[i+1]],
                        was_corrected=was_corrected,
                        ambiguity_detected=False,
                    )
                    matched_people.append(person_obj)
                    if was_corrected:
                        corrections.append(person_obj)
                        logger.info("Corrected Person (2-gram): '%s' -> '%s' (Score: %.1f)", bigram, canonical, score)

                    unmatched_tokens[i] = canonical
                    unmatched_tokens[i+1] = ""
                    match_found = True
                    i += 2
                    continue

            token = tokens[i]

            # 1. Check joined token split (e.g. 'अमीतशाह')
            joined_split = self._split_joined_token(token)
            if joined_split:
                canonical, split_text, score = joined_split
                person_obj = MatchedPerson(
                    canonical_name=canonical,
                    original_text=token,
                    confidence=float(score),
                    matched_tokens=[token],
                    was_corrected=True,
                    ambiguity_detected=False,
                )
                matched_people.append(person_obj)
                corrections.append(person_obj)
                logger.info("Split Joined Person: '%s' -> '%s' (Score: %.1f)", token, canonical, score)
                unmatched_tokens[i] = canonical
                match_found = True
                i += 1
                continue

            # 2. Check full surface alias match
            best_single = process.extractOne(token, surface_choices, scorer=fuzz.ratio, score_cutoff=self.min_confidence_threshold)
            if best_single:
                matched_surface, score, _ = best_single
                canonical = self.surface_to_canonical[matched_surface]
                was_corrected = (token != canonical)

                person_obj = MatchedPerson(
                    canonical_name=canonical,
                    original_text=token,
                    confidence=float(score),
                    matched_tokens=[token],
                    was_corrected=was_corrected,
                    ambiguity_detected=False,
                )
                matched_people.append(person_obj)
                if was_corrected:
                    corrections.append(person_obj)
                    logger.info("Corrected Person Token: '%s' -> '%s' (Score: %.1f)", token, canonical, score)
                unmatched_tokens[i] = canonical
                match_found = True
                i += 1
                continue

            # 3. Check surname / partial name matching & ambiguity protection
            surname_choices = list(self.surname_index.keys())
            best_surname = process.extractOne(token, surname_choices, scorer=fuzz.ratio, score_cutoff=75.0)
            if best_surname:
                sur_name, score, _ = best_surname
                matching_canonicals = list(self.surname_index[sur_name])

                if len(matching_canonicals) == 1:
                    canonical = matching_canonicals[0]
                    person_obj = MatchedPerson(
                        canonical_name=canonical,
                        original_text=token,
                        confidence=float(score),
                        matched_tokens=[token],
                        was_corrected=True,
                        ambiguity_detected=False,
                    )
                    matched_people.append(person_obj)
                    corrections.append(person_obj)
                    logger.info("Resolved Unambiguous Surname: '%s' -> '%s' (Score: %.1f)", token, canonical, score)
                    unmatched_tokens[i] = canonical
                    match_found = True
                elif len(matching_canonicals) > 1:
                    person_obj = MatchedPerson(
                        canonical_name=sur_name,
                        original_text=token,
                        confidence=float(score),
                        matched_tokens=[token],
                        was_corrected=True,
                        ambiguity_detected=True,
                    )
                    matched_people.append(person_obj)
                    corrections.append(person_obj)
                    logger.warning("Ambiguity Detected for Surname '%s' (Matches: %s)", token, matching_canonicals)
                    unmatched_tokens[i] = token
                    match_found = True

            i += 1

        cleaned_tokens = [t for t in unmatched_tokens if t]
        normalized_text = " ".join(cleaned_tokens)

        return PersonNormalizationResult(
            original_query=query,
            normalized_query=normalized_text,
            matched_people=matched_people,
            corrections=corrections,
            unmatched_tokens=[t for t in tokens if t not in [p.original_text for p in matched_people]],
        )
