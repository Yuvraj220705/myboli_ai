"""Sprint 5.0.1: Conversation Router & User Interaction Layer for Maayboli AI.

Provides deterministic, sub-millisecond classification of non-RAG conversational intents
(greetings, gratitude, farewells, help, identity, capability) to improve UX and avoid
unnecessary retrieval or LLM generation calls.
"""

from dataclasses import dataclass, field
import json
import logging
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
PATTERNS_PATH = CONFIG_DIR / "conversation_patterns.json"

__all__ = [
    "ConversationIntent",
    "ConversationRouter",
]


@dataclass
class ConversationIntent:
    """Structured result object produced by ConversationRouter classification.

    Attributes:
        intent_type: String identifier ('GREETING', 'GRATITUDE', 'FAREWELL', 'HELP', 'IDENTITY', 'CAPABILITY', 'NEWS_QUERY').
        confidence: Match confidence float score (1.0 for deterministic match, 0.0 for fallthrough).
        normalized_message: Cleaned and normalized input string.
        should_use_rag: Boolean flag indicating if input should enter existing RAG pipeline.
        response_text: Deterministic predefined response string for non-RAG intents.
        reason: Explanation string for audit logging and telemetry.
    """
    intent_type: str = "NEWS_QUERY"
    confidence: float = 0.0
    normalized_message: str = ""
    should_use_rag: bool = True
    response_text: str = ""
    reason: str = "Default fallthrough to RAG pipeline for news retrieval."


# Predefined Deterministic Responses
PREDEFINED_RESPONSES: Dict[str, str] = {
    "GREETING": (
        "नमस्कार! 😊\n\n"
        "मी मायबोली AI आहे.\n\n"
        "मी महाराष्ट्रातील स्थानिक प्रकाशित बातम्यांवर आधारित माहिती देऊ शकतो.\n\n"
        "आज तुम्हाला कोणत्या विषयाबद्दल माहिती हवी आहे?"
    ),
    "GRATITUDE": (
        "तुमचं स्वागत आहे! 😊\n\n"
        "आणखी काही मदत हवी असल्यास नक्की विचारा."
    ),
    "FAREWELL": (
        "धन्यवाद! 😊\n\n"
        "पुन्हा भेटूया.\n\n"
        "तुमचा दिवस आनंदाचा जावो."
    ),
    "IDENTITY": (
        "मी मायबोली AI आहे.\n\n"
        "मी महाराष्ट्रातील स्थानिक प्रकाशित बातम्यांवर आधारित माहिती देणारा AI सहाय्यक आहे."
    ),
    "CAPABILITY": (
        "मी खालील विषयांवरील प्रकाशित बातम्यांबद्दल माहिती देऊ शकतो:\n\n"
        "• जिल्हानिहाय बातम्या\n"
        "• राजकारण\n"
        "• हवामान\n"
        "• अपघात\n"
        "• शेती\n"
        "• स्थानिक घडामोडी\n"
        "• प्रमुख व्यक्तींशी संबंधित बातम्या\n\n"
        "तुम्ही मला नैसर्गिक भाषेत प्रश्न विचारू शकता."
    ),
    "HELP": (
        "मायबोली AI सह संभाषण करण्यासाठी तुम्ही मला खालीलप्रमाणे प्रश्न विचारू शकता:\n\n"
        "१. \"पुण्यात आज पावसाची काय स्थिती आहे?\"\n"
        "२. \"अमित शाह यांनी नागपूर दौऱ्यात काय घोषणा केल्या?\"\n"
        "३. \"कोल्हापूर जिल्ह्यातील पूर परिस्थितीची बातमी सांगा.\"\n"
        "४. \"देवेंद्र फडणवीस आणि एकनाथ शिंदे यांची बैठक कुठे झाली?\"\n"
        "५. \"सिंधुदुर्ग जिल्ह्यात पर्यटन वाढीसाठी कोणते निर्णय घेतले?\"\n"
        "६. \"महाराष्ट्रातील एसटी बस प्रवाशांसाठी काय नवीन सवलती आहेत?\"\n"
        "७. \"रत्नागिरी जिल्ह्यात काजू बागायतदारांसाठी काय योजना आहे?\"\n"
        "८. \"नाशिकमधील कुंभमेळा नियोजनाबद्दल काय बातमी आहे?\"\n\n"
        "कृपया तुमचा प्रश्न मराठीत टाईप करा! 😊"
    ),
}


class ConversationRouter:
    """Deterministic, config-driven router that classifies user inputs prior to RAG execution."""

    def __init__(self, config_path: Path = PATTERNS_PATH):
        """Initialize ConversationRouter by loading JSON pattern configurations."""
        self.config_path = config_path
        self.intent_rules: List[Dict[str, Any]] = []
        self._load_patterns()

    def _load_patterns(self) -> None:
        """Load intent recognition patterns and phrases from JSON configuration file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for rule_key, rule_val in data.items():
                        intent_type = rule_val.get("intent", rule_key.upper())
                        exact_phrases = set(p.lower().strip() for p in rule_val.get("exact_phrases", []))
                        pattern_strs = rule_val.get("patterns", [])
                        compiled_pats = [re.compile(p, re.IGNORECASE) for p in pattern_strs]
                        self.intent_rules.append({
                            "intent": intent_type,
                            "exact_phrases": exact_phrases,
                            "patterns": compiled_pats,
                        })
                    logger.info("Loaded %d intent rules from %s", len(self.intent_rules), self.config_path.name)
                    return
            except Exception as e:
                logger.error("Failed to load conversation patterns from %s: %s", self.config_path, e)

        # Fallback default rules if JSON config is missing
        logger.warning("Using fallback hardcoded conversation rules.")
        self.intent_rules = [
            {
                "intent": "GREETING",
                "exact_phrases": {"hi", "hello", "hey", "hii", "हाय", "नमस्कार", "नमस्ते"},
                "patterns": [re.compile(r"^(hi|hello|hey|hii+)(\s+there|\s+bot)?$", re.IGNORECASE), re.compile(r"^(नमस्कार|नमस्ते|हाय)$")],
            },
            {
                "intent": "GRATITUDE",
                "exact_phrases": {"thanks", "thank you", "धन्यवाद", "खूप धन्यवाद", "थँक्यू"},
                "patterns": [re.compile(r"^(thanks|thank\s+you|thx)$", re.IGNORECASE), re.compile(r"^(धन्यवाद|खूप\s+धन्यवाद)$")],
            },
            {
                "intent": "FAREWELL",
                "exact_phrases": {"bye", "goodbye", "बाय", "निघतो", "पुन्हा भेटू"},
                "patterns": [re.compile(r"^(bye|goodbye)$", re.IGNORECASE), re.compile(r"^(बाय|निघतो)$")],
            },
            {
                "intent": "IDENTITY",
                "exact_phrases": {"who are you", "तू कोण आहेस", "तुझे नाव काय आहे"},
                "patterns": [re.compile(r"who\s+(are\s+you|made\s+you)", re.IGNORECASE), re.compile(r"तू\s+कोण\s+आहेस")],
            },
            {
                "intent": "CAPABILITY",
                "exact_phrases": {"what can you do", "तू काय करू शकतोस"},
                "patterns": [re.compile(r"what\s+can\s+you\s+do", re.IGNORECASE), re.compile(r"तू\s+काय\s+करू\s+शकतोस")],
            },
            {
                "intent": "HELP",
                "exact_phrases": {"help", "मदत", "तुझी मदत कशी मिळेल"},
                "patterns": [re.compile(r"^(help|मदत)$", re.IGNORECASE), re.compile(r"how\s+can\s+you\s+help", re.IGNORECASE)],
            },
        ]

    def route_message(self, message: str) -> ConversationIntent:
        """Classify incoming user message into conversational intent or RAG news query.

        Args:
            message: Input text string from user.

        Returns:
            ConversationIntent: Structured classification result.
        """
        if not message or not message.strip():
            return ConversationIntent(
                intent_type="GREETING",
                confidence=1.0,
                normalized_message="",
                should_use_rag=False,
                response_text=PREDEFINED_RESPONSES["GREETING"],
                reason="Empty input message received. Triggered default greeting.",
            )

        clean_msg = message.strip()
        lower_msg = clean_msg.lower()

        # Step 1: Check Exact Phrases & Regex Patterns
        for rule in self.intent_rules:
            intent_type = rule["intent"]

            # Exact match check
            if lower_msg in rule["exact_phrases"]:
                response_text = PREDEFINED_RESPONSES.get(intent_type, "")
                logger.info("ROUTED by ConversationRouter: intent='%s' method='exact_match' msg='%s'", intent_type, clean_msg[:30])
                return ConversationIntent(
                    intent_type=intent_type,
                    confidence=1.0,
                    normalized_message=clean_msg,
                    should_use_rag=False,
                    response_text=response_text,
                    reason=f"Matched exact conversational phrase for {intent_type}.",
                )

            # Regex pattern match check
            for pattern in rule["patterns"]:
                if pattern.search(clean_msg):
                    response_text = PREDEFINED_RESPONSES.get(intent_type, "")
                    logger.info("ROUTED by ConversationRouter: intent='%s' method='regex' msg='%s'", intent_type, clean_msg[:30])
                    return ConversationIntent(
                        intent_type=intent_type,
                        confidence=1.0,
                        normalized_message=clean_msg,
                        should_use_rag=False,
                        response_text=response_text,
                        reason=f"Matched regex pattern for {intent_type}.",
                    )

        # Step 2: Fallthrough to RAG News Retrieval Pipeline
        logger.debug("PASSED ConversationRouter: msg='%s' -> NEWS_QUERY", clean_msg[:30])
        return ConversationIntent(
            intent_type="NEWS_QUERY",
            confidence=0.0,
            normalized_message=clean_msg,
            should_use_rag=True,
            response_text="",
            reason="Input message did not match non-RAG conversational rules. Routing to RAG pipeline.",
        )
