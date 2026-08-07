"""Sprint 5.0.1: Comprehensive Unit Test Suite for Conversation Router & User Interaction Layer.

Tests ConversationRouter classification across Greetings, Gratitude, Farewell, Identity,
Capability, Help, News Queries, Code-mixed inputs, and Latency Benchmarks.
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from conversation_router import ConversationIntent, ConversationRouter


class TestConversationRouter(unittest.TestCase):
    """Unit test suite for ConversationRouter."""

    @classmethod
    def setUpClass(cls):
        """Set up ConversationRouter instance."""
        cls.router = ConversationRouter()

    def test_greeting_detection(self):
        """Verify that English and Marathi greetings are classified as GREETING."""
        inputs = [
            "Hi",
            "Hello",
            "Hey",
            "hii",
            "हाय",
            "नमस्कार",
            "नमस्ते",
            "Good Morning",
            "Good Evening",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertIsInstance(res, ConversationIntent)
                self.assertEqual(res.intent_type, "GREETING")
                self.assertFalse(res.should_use_rag)
                self.assertEqual(res.confidence, 1.0)
                self.assertIn("मायबोली AI", res.response_text)

    def test_gratitude_detection(self):
        """Verify that gratitude phrases are classified as GRATITUDE."""
        inputs = [
            "Thanks",
            "Thank you",
            "धन्यवाद",
            "खूप धन्यवाद",
            "Thank you so much",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertEqual(res.intent_type, "GRATITUDE")
                self.assertFalse(res.should_use_rag)
                self.assertIn("स्वागत", res.response_text)

    def test_farewell_detection(self):
        """Verify that farewell phrases are classified as FAREWELL."""
        inputs = [
            "Bye",
            "Goodbye",
            "See you",
            "बाय",
            "निघतो",
            "पुन्हा भेटू",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertEqual(res.intent_type, "FAREWELL")
                self.assertFalse(res.should_use_rag)
                self.assertIn("दिवस आनंदाचा जावो", res.response_text)

    def test_identity_detection(self):
        """Verify that identity questions are classified as IDENTITY."""
        inputs = [
            "Who are you?",
            "तू कोण आहेस?",
            "Who made you?",
            "तुझे नाव काय आहे?",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertEqual(res.intent_type, "IDENTITY")
                self.assertFalse(res.should_use_rag)
                self.assertIn("मी मायबोली AI आहे", res.response_text)

    def test_capability_detection(self):
        """Verify that capability questions are classified as CAPABILITY."""
        inputs = [
            "What can you do?",
            "तू काय करू शकतोस?",
            "Which news do you provide?",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertEqual(res.intent_type, "CAPABILITY")
                self.assertFalse(res.should_use_rag)
                self.assertIn("प्रकाशित बातम्यांबद्दल माहिती", res.response_text)

    def test_help_detection(self):
        """Verify that help requests are classified as HELP with example queries."""
        inputs = [
            "Help",
            "मदत",
            "तुझी मदत कशी मिळेल?",
            "How can you help?",
        ]
        for msg in inputs:
            with self.subTest(message=msg):
                res = self.router.route_message(msg)
                self.assertEqual(res.intent_type, "HELP")
                self.assertFalse(res.should_use_rag)
                self.assertIn("पुण्यात आज पावसाची काय स्थिती आहे?", res.response_text)

    def test_news_query_routing_fallthrough(self):
        """Verify that genuine Marathi news queries fall through to NEWS_QUERY (RAG)."""
        queries = [
            "पुण्यात आज पावसाची काय स्थिती आहे?",
            "अमित शाह यांनी नागपूर दौऱ्यात काय विधान केले?",
            "कोल्हापूर जिल्ह्यात पावसामुळे पूर आलेला आहे का?",
            "महाराष्ट्रातील मराठा आरक्षणाबाबत काय बातम्या आहेत?",
            "सिंधुदुर्ग जिल्ह्यात नवीन उड्डाणपुलाचे उद्घाटन झाले का?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = self.router.route_message(q)
                self.assertEqual(res.intent_type, "NEWS_QUERY")
                self.assertTrue(res.should_use_rag)
                self.assertEqual(res.confidence, 0.0)
                self.assertEqual(res.response_text, "")

    def test_empty_and_whitespace_input(self):
        """Verify that empty or whitespace inputs trigger default greeting."""
        res = self.router.route_message("   ")
        self.assertEqual(res.intent_type, "GREETING")
        self.assertFalse(res.should_use_rag)

    def test_sub_millisecond_latency(self):
        """Verify that routing execution completes in under 0.1 milliseconds average."""
        sample_msg = "तुझी मदत कशी मिळेल?"
        iterations = 1000
        t0 = time.perf_counter()
        for _ in range(iterations):
            self.router.route_message(sample_msg)
        t1 = time.perf_counter()

        avg_latency_ms = ((t1 - t0) / iterations) * 1000.0
        self.assertLess(avg_latency_ms, 0.1, f"Average latency ({avg_latency_ms:.4f}ms) exceeds 0.1ms NFR target")


if __name__ == "__main__":
    unittest.main()
