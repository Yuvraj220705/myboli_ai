"""Sprint 4.0.0: Comprehensive Unit Test Suite for Unknown Entity Guardrail.

Tests UnknownEntityGuard inspection logic across supported regional queries,
unsupported foreign entities, sports players, tech brands, companies, products,
latency benchmarks, and false positive prevention.
"""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from entity_normalizer import DistrictNormalizer, PersonNormalizer, WordNormalizer
from query_processor import process_query
from unknown_entity_guard import UnknownEntityGuard, UnknownEntityResult


class TestUnknownEntityGuard(unittest.TestCase):
    """Unit test suite for UnknownEntityGuard."""

    @classmethod
    def setUpClass(cls):
        """Set up normalizer singletons and guard instance."""
        cls.district_norm = DistrictNormalizer()
        cls.person_norm = PersonNormalizer()
        cls.word_norm = WordNormalizer()
        cls.guard = UnknownEntityGuard(cls.district_norm, cls.person_norm, cls.word_norm)

    def test_supported_maharashtra_queries_pass(self):
        """Verify that valid Maharashtrian queries pass the guard without blocking."""
        queries = [
            "अमित शाह यांनी पुण्यात काय भाषण दिले?",
            "सिंधुदुर्ग जिल्ह्यात आज काय विशेष घडामोडी आहेत?",
            "कोल्हापूर जिल्ह्यात पावसामुळे पूरस्थिती निर्माण झाली आहे का?",
            "देवेंद्र फडणवीस नागपूर दौरा अपडेट",
            "महाराष्ट्रातील हवामान अंदाज आणि पाऊस",
            "पुण्यातील वाहतूक कोंडी आणि अपघातांबद्दल काय बातम्या आहेत?",
            "शरद पवार आणि उद्धव ठाकरे यांची संयुक्त बैठक",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = self.guard.inspect_query(q)
                self.assertIsInstance(res, UnknownEntityResult)
                self.assertFalse(res.should_block, f"Should NOT block valid regional query: '{q}'")
                self.assertEqual(res.confidence, "HIGH")

    def test_unsupported_foreign_leaders_blocked(self):
        """Verify that queries containing foreign political leaders are blocked."""
        queries = [
            "अमेरिकेचे अध्यक्ष ज्यो बायडेन भारतात कधी येणार?",
            "डोनाल्ड ट्रम्प यांच्या निवडणुकीतील विधानाबाबत बातमी",
            "युक्रेन आणि रशिया युद्धाबाबत संयुक्त राष्ट्रांची बैठक",
            "अमेरिकेत निवडणुकांचा निकाल काय लागला?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = self.guard.inspect_query(q)
                self.assertTrue(res.should_block, f"MUST block foreign leader/country query: '{q}'")
                self.assertIn("Unsupported critical entity", res.reason)

    def test_unsupported_sports_entities_blocked(self):
        """Verify that global sports players and non-regional events are blocked."""
        queries = [
            "क्रिस्टियानो रोनाल्डोच्या फुटबॉल सामन्याचा निकाल सांगा",
            "आयपीएल २०२६ च्या लिलावात सर्वात महागडा खेळाडू कोण?",
            "टोकियो ऑलिम्पिकमध्ये नीरज चोप्राने सुवर्णपदक कसे जिंकले?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = self.guard.inspect_query(q)
                self.assertTrue(res.should_block, f"MUST block foreign sports query: '{q}'")

    def test_unsupported_companies_and_tech_blocked(self):
        """Verify that foreign tech companies, products, and crypto queries are blocked."""
        queries = [
            "इलॉन मस्क यांच्या टेस्ला कारची भारतात विक्री कधी सुरू होणार?",
            "गूगल कंपनीची नवी AI तंत्रज्ञान घोषणा आणि फीचर्स",
            "ओपनएआय कडून नवीन मॉडेल लॉन्च",
            "ॲपल व्हिजन प्रो ची किंमत आणि फीचर्स सांगा",
            "बिटकॉइन आणि क्रिप्टो करन्सीचे आजचे दर काय आहेत?",
        ]
        for q in queries:
            with self.subTest(query=q):
                res = self.guard.inspect_query(q)
                self.assertTrue(res.should_block, f"MUST block tech/company query: '{q}'")

    def test_query_processor_integration(self):
        """Verify that QueryProcessor attaches UnknownEntityResult to QueryInfo."""
        q_supported = "पुण्यात पावसाची काय स्थिती आहे?"
        info_supported = process_query(q_supported)
        self.assertIsNotNone(info_supported.unknown_entity_result)
        self.assertFalse(info_supported.unknown_entity_result.should_block)

        q_unsupported = "अमेरिकेचे अध्यक्ष ज्यो बायडेन यांचा भारत दौरा कधी आहे?"
        info_unsupported = process_query(q_unsupported)
        self.assertIsNotNone(info_unsupported.unknown_entity_result)
        self.assertTrue(info_unsupported.unknown_entity_result.should_block)

    def test_multiple_foreign_entities_detected(self):
        """Verify that multi-entity queries detect ALL foreign entities, not just the first one."""
        query = "जो बायडेन, डोनाल्ड ट्रम्प आणि इलॉन मस्क यांची भेट होणार का?"
        res = self.guard.inspect_query(query)
        self.assertTrue(res.should_block)
        # Verify multiple critical entities are extracted
        self.assertGreaterEqual(len(res.critical_entities), 2)

    def test_guard_execution_latency(self):
        """Benchmark that guard inspection completes in under 1 millisecond average."""
        sample_query = "अमेरिकेचे अध्यक्ष ज्यो बायडेन भारतात कधी येणार?"
        iterations = 100
        t0 = time.perf_counter()
        for _ in range(iterations):
            self.guard.inspect_query(sample_query)
        t1 = time.perf_counter()

        avg_latency_ms = ((t1 - t0) / iterations) * 1000.0
        self.assertLess(avg_latency_ms, 1.0, f"Average latency ({avg_latency_ms:.3f}ms) exceeds 1.0ms requirement")


if __name__ == "__main__":
    unittest.main()
