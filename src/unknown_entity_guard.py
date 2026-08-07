"""Sprint 4.0.0: Unknown Entity Guardrail for Maayboli AI.

Provides deterministic detection of unsupported foreign entities, companies, products,
and out-of-scope proper nouns to prevent keyword over-matching in MySQL retrieval.
"""

from dataclasses import dataclass, field
import logging
import re
from typing import Any, List, Optional, Set

from entity_normalizer import DistrictNormalizer, PersonNormalizer, WordNormalizer

logger = logging.getLogger(__name__)

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


# Generic Supporting Terms (nouns, titles, verbs, query fillers that do NOT form primary entities on their own)
SUPPORTING_TERMS_SET: Set[str] = {
    # Titles & Roles
    "अध्यक्ष", "प्रदेशाध्यक्ष", "पंतप्रधान", "मुख्यमंत्री", "मंत्री", "खासदार", "आमदार", "नेते", "अधिकारी", "पोलिस", "पोलीस",
    # Actions & Events
    "दौरा", "भाषण", "सभेत", "सभा", "बैठक", "बैठकीत", "निर्णय", "घोषणा", "विधान", "अपघात", "पाऊस", "हवामान", "वेळापत्रक",
    "निकालाची", "निकाल", "आरक्षण", "कर्जमाफी", "निवडणूक", "भरती", "आंदोलन", "कुंभमेळा", "सामना", "लिलाव", "खेळाडू",
    # Geography & General Context
    "महाराष्ट्र", "महाराष्ट्रातील", "महाराष्ट्रात", "भारत", "भारतात", "भारतातील", "जिल्हा", "जिल्ह्यात", "शहर", "शहरातील",
    # Conversational & Grammar Fillers
    "सांगा", "माहिती", "बातमी", "बातम्या", "अपडेट", "काय", "आहे", "नाही", "कधी", "कसे", "कोण", "कशा", "आज", "काल", "आजची",
    "नवीन", "ताजी", "ताज्या", "विशेष", "सविस्तर", "मला", "त्याबद्दल", "घेऊन", "येणार", "झालं", "झाली", "केले", "होते",
    "विषयी", "संबंधी", "बद्दल", "उत्तर", "प्रश्न", "दर", "किंमत", "घसरण", "वाढ",
}

# Explicit Foreign / Out-of-Scope Proper Noun Entities (Transliterations & English terms)
KNOWN_FOREIGN_CRITICAL_PATTERNS: List[re.Pattern] = [
    # Global Political Leaders & Figures
    re.compile(r"\b(जो|ज्यो|अध्यक्ष)?\s*(बायडेन|बायडन|biden)\b", re.IGNORECASE),
    re.compile(r"\b(डोनाल्ड)?\s*(ट्रम्प|trump)\b", re.IGNORECASE),
    re.compile(r"\b(कमला)?\s*(हॅरिस|harris)\b", re.IGNORECASE),
    re.compile(r"\b(व्लादिमीर|पुतीन)?\s*(पुतिन|putin)\b", re.IGNORECASE),
    re.compile(r"\b(व्होलोडिमिर)?\s*(झेलेंस्की|zelenskyy|zelensky)\b", re.IGNORECASE),
    re.compile(r"\b(ऋषी|रिशी)?\s*(सुनक|sunak)\b", re.IGNORECASE),
    re.compile(r"\b(इमॅन्युएल)?\s*(मॅक्रॉन|macron)\b", re.IGNORECASE),
    re.compile(r"\b(बेंजामिन)?\s*(नेतान्याहू|नेतान्याहु|netanyahu)\b", re.IGNORECASE),
    re.compile(r"\b(जस्टिन)?\s*(ट्रुडो|ट्रूडो|trudeau)\b", re.IGNORECASE),
    re.compile(r"\b(शी)?\s*(जिनपिंग|jinping)\b", re.IGNORECASE),
    re.compile(r"\b(इलॉन|एलोन)?\s*(मस्क|musk)\b", re.IGNORECASE),

    # International Countries & Global Cities outside Maharashtra regional scope
    re.compile(r"\b(अमेरिका|अमेरिकेचे|अमेरिकेत|usa|us|america)\b", re.IGNORECASE),
    re.compile(r"\b(रशिया|रशियातील|russia)\b", re.IGNORECASE),
    re.compile(r"\b(युक्रेन|युक्रेनियन|ukraine)\b", re.IGNORECASE),
    re.compile(r"\b(कॅनडा|कॅनडात|कॅनडातील|canada)\b", re.IGNORECASE),
    re.compile(r"\b(इस्रायल|इस्राईल|israel)\b", re.IGNORECASE),
    re.compile(r"\b(टोकियो|tokyo)\b", re.IGNORECASE),
    re.compile(r"\b(लंडन|लंडनमध्ये|london)\b", re.IGNORECASE),
    re.compile(r"\b(पॅरिस|paris)\b", re.IGNORECASE),
    re.compile(r"\b(वॉशिंग्टन|washington)\b", re.IGNORECASE),
    re.compile(r"\b(दुबई|dubai)\b", re.IGNORECASE),
    re.compile(r"\b(सिडनी|sydney)\b", re.IGNORECASE),
    re.compile(r"\b(अँटार्टिका|अंटार्टिका|antarctica)\b", re.IGNORECASE),
    re.compile(r"\b(चंद्रावर|चंद्र|moon)\b", re.IGNORECASE),

    # Tech Giants, Companies & Products
    re.compile(r"\b(गुगल|गूगल|google)\s*(gemini)?\b", re.IGNORECASE),
    re.compile(r"\b(टेस्ला|tesla)\b", re.IGNORECASE),
    re.compile(r"\b(ओपनएआय|openai|chatgpt)\b", re.IGNORECASE),
    re.compile(r"\b(ॲपल|अ‍ॅपल|apple)\s*(व्हिजन|vision)?\s*(प्रो|pro)?\b", re.IGNORECASE),
    re.compile(r"\b(मायक्रोसॉफ्ट|microsoft)\s*(विंडोज|windows)?\b", re.IGNORECASE),
    re.compile(r"\b(मेटा|meta)\s*(थ्रेड्स|threads)?\b", re.IGNORECASE),
    re.compile(r"\b(अ‍ॅमेझॉन|ॲमेझॉन|amazon)\s*(एडब्ल्यूएस|aws)?\b", re.IGNORECASE),
    re.compile(r"\b(स्टारलिंक|starlink)\b", re.IGNORECASE),
    re.compile(r"\b(स्पेसएक्स|spacex)\b", re.IGNORECASE),
    re.compile(r"\b(एनव्हिडिया|nvidia)\b", re.IGNORECASE),
    re.compile(r"\b(सॅमसंग|samsung)\b", re.IGNORECASE),
    re.compile(r"\b(सोनी|sony)\s*(प्लेस्टेशन|playstation)?\b", re.IGNORECASE),

    # Global Sports, Events & Entertainment Awards
    re.compile(r"\b(क्रिस्टियानो)?\s*(रोनाल्डो|ronaldo)\b", re.IGNORECASE),
    re.compile(r"\b(लिओनेल)?\s*(मेस्सी|messi)\b", re.IGNORECASE),
    re.compile(r"\b(नीरज)?\s*(चोप्रा|chopra)\b", re.IGNORECASE),
    re.compile(r"\b(आयपीएल|ipl)\s*(लिलाव|auction)?\b", re.IGNORECASE),
    re.compile(r"\b(ऑलिम्पिक|ऑलिंपिक|olympics)\b", re.IGNORECASE),
    re.compile(r"\b(फीफा|fifa)\s*(वर्ल्ड|world)?\s*(कप|cup)?\b", re.IGNORECASE),
    re.compile(r"\b(ऑस्कर|oscar)\s*(अवॉर्ड्स|awards)?\b", re.IGNORECASE),
    re.compile(r"\b(ग्रॅमी|grammy)\s*(अवॉर्ड्स|awards)?\b", re.IGNORECASE),
    re.compile(r"\b(सुपर\s*बाऊल|super\s*bowl)\b", re.IGNORECASE),
    re.compile(r"\b(विम्बल्डन|wimbledon)\b", re.IGNORECASE),
    re.compile(r"\b(फॉर्म्युला\s*१|formula\s*1|f1)\b", re.IGNORECASE),
    re.compile(r"\b(एनबीए|nba)\b", re.IGNORECASE),
    re.compile(r"\b(युएफसी|ufc)\b", re.IGNORECASE),

    # Crypto, Global Markets & International Orgs
    re.compile(r"\b(बिटकॉइन|बिटकॉईन|bitcoin|crypto)\b", re.IGNORECASE),
    re.compile(r"\b(इथेरियम|ethereum)\b", re.IGNORECASE),
    re.compile(r"\b(फेडरल\s*रिझर्व्ह|federal\s*reserve)\b", re.IGNORECASE),
    re.compile(r"\b(वॉल\s*स्ट्रीट|wall\s*street)\b", re.IGNORECASE),
    re.compile(r"\b(नाटो|nato)\b", re.IGNORECASE),
    re.compile(r"\b(युरोपियन\s*युनियन|european\s*union|eu)\b", re.IGNORECASE),
    re.compile(r"\b(डब्ल्यूएचओ|who)\b", re.IGNORECASE),
    re.compile(r"\b(जी२०|g20)\b", re.IGNORECASE),
    re.compile(r"\b(नासा|nasa)\b", re.IGNORECASE),
]


class UnknownEntityGuard:
    """Deterministic guardrail component that inspects user queries for unsupported entities."""

    def __init__(
        self,
        district_normalizer: Optional[DistrictNormalizer] = None,
        person_normalizer: Optional[PersonNormalizer] = None,
        word_normalizer: Optional[WordNormalizer] = None,
    ):
        """Initialize UnknownEntityGuard by reusing existing entity normalizer instances."""
        self.district_normalizer = district_normalizer or DistrictNormalizer()
        self.person_normalizer = person_normalizer or PersonNormalizer()
        self.word_normalizer = word_normalizer or WordNormalizer()

    def inspect_query(self, query: str, query_info: Optional[Any] = None) -> UnknownEntityResult:
        """Inspect query to identify known vs unknown critical entities and determine blocking.

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

        # Step 2: Check explicit Foreign / Out-of-Scope Critical Patterns
        foreign_match_found = False
        detected_foreign_entity = ""
        for pattern in KNOWN_FOREIGN_CRITICAL_PATTERNS:
            match = pattern.search(clean_q)
            if match:
                foreign_match_found = True
                detected_foreign_entity = match.group(0).strip()
                critical_entities.append(detected_foreign_entity)
                unknown_entities.append(detected_foreign_entity)
                break

        # Step 3: Classify remaining tokens into Supporting Terms vs Unknown Tokens
        for token in tokens:
            token_clean = token.strip()
            if not token_clean:
                continue

            # Check if token is in supporting terms set
            if token_clean in SUPPORTING_TERMS_SET or any(sup in token_clean for sup in ["बातमी", "पाऊस", "सभा", "दौरा", "अपघात"]):
                supporting_terms.append(token_clean)
                continue

            # Check English unrecognized words
            if re.match(r"^[a-zA-Z0-9]+$", token_clean):
                # Common mapped English terms like Pune, rain, politics, news are supported
                if token_clean.lower() in {"pune", "sindhudurg", "kolhapur", "ratnagiri", "mumbai", "nagpur", "rain", "politics", "news", "status", "update", "visit", "speech"}:
                    known_entities.append(token_clean)
                else:
                    critical_entities.append(token_clean)
                    unknown_entities.append(token_clean)

        # Step 4: Decision Logic
        if foreign_match_found or (len(critical_entities) > 0 and len(known_entities) == 0):
            primary_entity = critical_entities[0] if critical_entities else "Foreign/Out-of-scope entity"
            reason = f"Unsupported critical entity detected: '{primary_entity}'. Query is out of Maharashtra regional news scope."
            logger.info("BLOCKED by UnknownEntityGuard: query='%s' reason='%s'", clean_q[:50], reason)
            return UnknownEntityResult(
                unknown_entities=list(set(unknown_entities)),
                known_entities=list(set(known_entities)),
                critical_entities=list(set(critical_entities)),
                supporting_terms=list(set(supporting_terms)),
                unknown_entity_ratio=1.0 if critical_entities else 0.0,
                should_block=True,
                reason=reason,
                confidence="HIGH",
            )

        logger.debug("PASSED UnknownEntityGuard: query='%s' known=%s", clean_q[:50], known_entities)
        return UnknownEntityResult(
            unknown_entities=list(set(unknown_entities)),
            known_entities=list(set(known_entities)),
            critical_entities=list(set(critical_entities)),
            supporting_terms=list(set(supporting_terms)),
            unknown_entity_ratio=0.0,
            should_block=False,
            reason="All critical entities are supported within Maharashtra regional scope.",
            confidence="HIGH",
        )
