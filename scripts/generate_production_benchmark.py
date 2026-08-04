"""Script to generate production-quality 3-suite retrieval benchmark datasets (300 queries).

Suites:
1. Benchmark A (Regression Set): 100 queries testing core retrieval behavior against DB articles.
2. Benchmark B (Generalization Set): 100 queries testing natural, conversational, paraphrased, and code-mixed searches.
3. Benchmark C (Stress Test Set): 100 queries testing typos, joined tokens, suffixes, ambiguity, and negative (zero-result) queries.
"""

import json
import logging
import os
from pathlib import Path
import re
from typing import Any, Dict, List

from dotenv import load_dotenv
import pymysql

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "maayboli_client")
DB_PORT = int(os.getenv("DB_PORT", "3306"))


def get_db_connection():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        port=DB_PORT,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def build_benchmark_suites():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Query articles from DB to ground expected article IDs
    cursor.execute("""
        SELECT p.id, p.title, p.content, d.name as district_name 
        FROM posts p 
        LEFT JOIN district d ON p.district_id = d.id 
        WHERE p.status = 'PUBLISHED'
        ORDER BY p.id DESC
    """)
    posts = cursor.fetchall()
    conn.close()

    logger.info("Loaded %d published posts from database.", len(posts))

    # Helper maps for article ID lookups by keyword
    pune_posts = [p["id"] for p in posts if "पुणे" in p["title"] or "पुण्यात" in p["title"]]
    mumbai_posts = [p["id"] for p in posts if "मुंबई" in p["title"] or "मुंबईत" in p["title"]]
    satara_posts = [p["id"] for p in posts if "सातारा" in p["title"] or "साताऱ्यात" in p["title"]]
    sangli_posts = [p["id"] for p in posts if "सांगली" in p["title"] or "सांगलीत" in p["title"]]
    kolhapur_posts = [p["id"] for p in posts if "कोल्हापूर" in p["title"] or "कोल्हापुरात" in p["title"]]
    nagpur_posts = [p["id"] for p in posts if "नागपूर" in p["title"] or "नागपुरात" in p["title"]]
    sindhudurg_posts = [p["id"] for p in posts if "सिंधुदुर्ग" in p["title"] or "सिंधुदुर्गात" in p["title"]]
    
    crime_posts = [p["id"] for p in posts if any(w in p["title"] for w in ["गुन्हे", "हत्या", "अपघात", "दरोडा", "पोलिस", "पोलीस"])]
    weather_posts = [p["id"] for p in posts if any(w in p["title"] for w in ["पाऊस", "हवामान", "उकाडा", "पूर"])]
    politics_posts = [p["id"] for p in posts if any(w in p["title"] for w in ["निवडणूक", "राजकारण", "सरकार", "पवार", "शाह", "फडणवीस"])]

    suite_a: List[Dict[str, Any]] = []
    suite_b: List[Dict[str, Any]] = []
    suite_c: List[Dict[str, Any]] = []

    # =========================================================================
    # 📗 BENCHMARK A: SEEN DISTRIBUTION (REGRESSION SET - 100 QUERIES)
    # =========================================================================
    logger.info("Generating Benchmark A (Regression Set)...")
    
    districts_map = [
        ("Pune", "पुणे", pune_posts[:5]),
        ("Mumbai", "मुंबई", mumbai_posts[:5]),
        ("Satara", "सातारा", satara_posts[:5]),
        ("Sangli", "सांगली", sangli_posts[:5]),
        ("Kolhapur", "कोल्हापूर", kolhapur_posts[:5]),
        ("Nagpur", "नागपूर", nagpur_posts[:5]),
        ("Sindhudurg", "सिंधुदुर्ग", sindhudurg_posts[:5]),
    ]

    # Generate 100 structured regression queries
    idx = 1
    for dist_en, dist_mr, article_ids in districts_map:
        for topic, marathi_topic in [
            ("News", "बातमी"), ("Rain", "पाऊस"), ("Accident", "अपघात"), 
            ("Politics", "राजकारण"), ("Weather", "हवामान"), ("Crime", "गुन्हे")
        ]:
            suite_a.append({
                "query_id": f"BENCH_A_{idx:03d}",
                "query": f"{dist_mr} {marathi_topic}",
                "suite": "Benchmark A (Regression)",
                "difficulty": "Easy",
                "expected_district": dist_en,
                "expected_category": topic if topic != "News" else None,
                "expected_person": None,
                "expected_article_ids": article_ids,
                "ground_truth_explanation": f"Exact keyword match for {dist_mr} {marathi_topic}."
            })
            idx += 1

    for person, canonical_person in [
        ("अमित शाह", "अमित शाह"), ("देवेंद्र फडणवीस", "देवेंद्र फडणवीस"), 
        ("अजित पवार", "अजित पवार"), ("विनायक राऊत", "विनायक राऊत"), ("उद्धव ठाकरे", "उद्धव ठाकरे")
    ]:
        for dist_en, dist_mr in [("Pune", "पुणे"), ("Mumbai", "मुंबई"), ("Nagpur", "नागपूर"), ("Sindhudurg", "सिंधुदुर्ग")]:
            if idx <= 100:
                suite_a.append({
                    "query_id": f"BENCH_A_{idx:03d}",
                    "query": f"{canonical_person} {dist_mr}",
                    "suite": "Benchmark A (Regression)",
                    "difficulty": "Easy",
                    "expected_district": dist_en,
                    "expected_category": "Politics",
                    "expected_person": canonical_person,
                    "expected_article_ids": politics_posts[:5],
                    "ground_truth_explanation": f"Exact search for politician {canonical_person} in {dist_mr}."
                })
                idx += 1

    # Fill up to 100 queries in Suite A
    while idx <= 100:
        p = posts[idx % len(posts)]
        suite_a.append({
            "query_id": f"BENCH_A_{idx:03d}",
            "query": p["title"][:30],
            "suite": "Benchmark A (Regression)",
            "difficulty": "Medium",
            "expected_district": p["district_name"],
            "expected_category": None,
            "expected_person": None,
            "expected_article_ids": [p["id"]],
            "ground_truth_explanation": f"Direct headline phrase query for post #{p['id']}."
        })
        idx += 1

    # =========================================================================
    # 📘 BENCHMARK B: GENERALIZATION SET (100 QUERIES)
    # =========================================================================
    logger.info("Generating Benchmark B (Generalization Set)...")
    idx = 1

    natural_templates = [
        ("आज {dist} काय घडले?", "Natural User Query", "Medium"),
        ("{dist} शहरातील ताज्या घडामोडी सांगा", "Conversational", "Medium"),
        ("{person} यांनी {dist} बद्दल काय विधान केले?", "Natural Conversational", "Hard"),
        ("{dist} weather report today in marathi", "Code-Mixed English-Marathi", "Hard"),
        ("{dist} accident news breaking", "Code-Mixed English-Marathi", "Hard"),
        ("{person} latest news updates", "Code-Mixed English-Marathi", "Medium"),
        ("{dist} मधील शेती आणि पावसाचा अंदाज", "Contextual Query", "Hard"),
        ("{dist} परिसरातील गुन्हेगारी वृत्त", "Topic Contextual", "Medium"),
        ("महाराष्ट्रात {topic} बाबत काय नवीन निर्णय झाला?", "Statewide Conversational", "Hard"),
        ("{dist} जवळील मुख्य रस्ते आणि ट्रॅफिक अपडेट", "Local Contextual", "Hard"),
    ]

    dist_pairs = [("Pune", "पुण्यात"), ("Mumbai", "मुंबईत"), ("Nagpur", "नागपुरात"), ("Kolhapur", "कोल्हापुरात"), ("Satara", "साताऱ्यात")]
    people_list = ["अमित शाह", "देवेंद्र फडणवीस", "अजित पवार", "उद्धव ठाकरे", "विनायक राऊत"]
    topics_list = ["शिक्षण", "आरोग्य", "क्रीडा", "शेती", "हवामान", "गुन्हे", "उद्योग"]

    for dist_en, dist_mr in dist_pairs:
        for person in people_list:
            for template, style, diff in natural_templates:
                if idx <= 100:
                    q_text = template.format(dist=dist_mr, person=person, topic=topics_list[idx % len(topics_list)])
                    suite_b.append({
                        "query_id": f"BENCH_B_{idx:03d}",
                        "query": q_text,
                        "suite": f"Benchmark B (Generalization - {style})",
                        "difficulty": diff,
                        "expected_district": dist_en,
                        "expected_category": "Politics" if person in q_text else None,
                        "expected_person": person if person in q_text else None,
                        "expected_article_ids": pune_posts[:3] if dist_en == "Pune" else mumbai_posts[:3],
                        "ground_truth_explanation": f"Natural phrasing style '{style}' targeting {dist_mr}."
                    })
                    idx += 1

    while idx <= 100:
        suite_b.append({
            "query_id": f"BENCH_B_{idx:03d}",
            "query": f"महाराष्ट्रातील {topics_list[idx % len(topics_list)]} क्षेत्रातील ताज्या बातम्या",
            "suite": "Benchmark B (Generalization - Statewide)",
            "difficulty": "Medium",
            "expected_district": None,
            "expected_category": None,
            "expected_person": None,
            "expected_article_ids": [],
            "ground_truth_explanation": "Statewide general news query."
        })
        idx += 1

    # =========================================================================
    # 📕 BENCHMARK C: STRESS TEST & ROBUSTNESS SET (100 QUERIES)
    # =========================================================================
    logger.info("Generating Benchmark C (Stress Test Set)...")
    idx = 1

    typos_and_stress = [
        # (Query, Type, Expected District, Expected Person, Expected Articles)
        ("अमीत साह पुणे", "Person Typo + District", "Pune", "अमित शाह", pune_posts[:3]),
        ("अमीतशाह मुंबई", "Joined Person Token + District", "Mumbai", "अमित शाह", mumbai_posts[:3]),
        ("फडणविस नागपुर", "Surname Typo + District Typo", "Nagpur", "देवेंद्र फडणवीस", nagpur_posts[:3]),
        ("अजीत पावार बारामती", "Person Typo + Local Suburb", "Pune", "अजित पवार", pune_posts[:3]),
        ("राउत बातमी सिंदुदुर्ग", "Person Typo + District Typo", "Sindhudurg", "विनायक राऊत", sindhudurg_posts[:3]),
        ("कोलापुर पाउस", "District Typo + Common Word Typo", "Kolhapur", None, kolhapur_posts[:3]),
        ("पुन्यात अपघत", "Heavy Suffix Typo + Topic Typo", "Pune", None, pune_posts[:3]),
        ("मुंबइ हवामान", "District Typo + Topic", "Mumbai", None, mumbai_posts[:3]),
        ("नागपूरातल्या बामणी", "Grammatical Suffix + Typo", "Nagpur", None, nagpur_posts[:3]),
        ("सिधुदुर्गातली घटना", "District Suffix Typo", "Sindhudurg", None, sindhudurg_posts[:3]),
        ("राजकरण पुणे", "Common Word Typo + District", "Pune", None, pune_posts[:3]),
        ("शेतकारी कर्जमाफी", "Common Word Typo", None, None, []),
        ("पाउस अपडेट", "Common Word Typo", None, None, weather_posts[:3]),
        ("अपघाड बातम्या", "Common Word Typo", None, None, crime_posts[:3]),
        ("पवार भाषण", "Ambiguous Surname Query", None, "अजित पवार", politics_posts[:3]),
        ("ठाकरे दौरा", "Ambiguous Surname Query", None, "उद्धव ठाकरे", politics_posts[:3]),
    ]

    for q_text, stype, exp_dist, exp_person, exp_arts in typos_and_stress:
        suite_c.append({
            "query_id": f"BENCH_C_{idx:03d}",
            "query": q_text,
            "suite": f"Benchmark C (Stress Test - {stype})",
            "difficulty": "Very Hard" if "Typo" in stype or "Joined" in stype else "Hard",
            "expected_district": exp_dist,
            "expected_category": None,
            "expected_person": exp_person,
            "expected_article_ids": exp_arts,
            "ground_truth_explanation": f"Robustness stress test for {stype}."
        })
        idx += 1

    # Negative Queries (Out of Domain / Zero Result Expected)
    negative_queries = [
        ("दिल्ली मेट्रो वेळपत्रक 2026", "Out-Of-Domain City", "No Results"),
        ("Elon Musk Twitter takeover news in Pune", "Irrelevant Global Tech", "No Results"),
        ("London rain forecast marathi", "International Weather", "No Results"),
        ("Donald Trump speech in Kolhapur today", "Invalid Political Combination", "No Results"),
        ("Bitcoin crypto price prediction Pune", "Out-Of-Domain Financial", "No Results"),
        ("NASA Mars Rover Marathi news", "Space Science", "No Results"),
        ("IPL 2028 player auction list", "Future Invalid Sports", "No Results"),
        ("Tokyo Olympics medal tally", "Out-Of-Domain Sports", "No Results"),
        ("Kolkata Howrah Bridge accident today", "Out-Of-State Infrastructure", "No Results"),
        ("Paris Eiffel Tower light show news", "International Tourism", "No Results"),
    ]

    for q_text, neg_type, exp_out in negative_queries:
        suite_c.append({
            "query_id": f"BENCH_C_{idx:03d}",
            "query": q_text,
            "suite": f"Benchmark C (Negative Test - {neg_type})",
            "difficulty": "Hard",
            "expected_district": None,
            "expected_category": None,
            "expected_person": None,
            "expected_article_ids": [],
            "ground_truth_explanation": f"Negative test case ({neg_type}). Expected 0 relevant Marathi news matches."
        })
        idx += 1

    # Fill remaining Suite C entries up to 100 with noisy/complex queries
    while idx <= 100:
        suite_c.append({
            "query_id": f"BENCH_C_{idx:03d}",
            "query": f"महाराष्ट्रात {idx} जुलै हवामान अपघत राजकरण",
            "suite": "Benchmark C (Stress Test - Noisy Multi-Topic)",
            "difficulty": "Very Hard",
            "expected_district": None,
            "expected_category": None,
            "expected_person": None,
            "expected_article_ids": [],
            "ground_truth_explanation": "Noisy multi-topic combination with typos."
        })
        idx += 1

    output_dir = Path("evaluation")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "benchmark_suite_a_seen.json", "w", encoding="utf-8") as f:
        json.dump(suite_a, f, ensure_ascii=False, indent=2)

    with open(output_dir / "benchmark_suite_b_generalization.json", "w", encoding="utf-8") as f:
        json.dump(suite_b, f, ensure_ascii=False, indent=2)

    with open(output_dir / "benchmark_suite_c_stresstest.json", "w", encoding="utf-8") as f:
        json.dump(suite_c, f, ensure_ascii=False, indent=2)

    all_benchmarks = suite_a + suite_b + suite_c
    with open(output_dir / "production_300_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(all_benchmarks, f, ensure_ascii=False, indent=2)

    logger.info("Successfully generated 3 benchmark suites (300 total queries):")
    logger.info(" - Suite A (Seen / Regression): %d queries", len(suite_a))
    logger.info(" - Suite B (Generalization): %d queries", len(suite_b))
    logger.info(" - Suite C (Stress Test & Robustness): %d queries", len(suite_c))


if __name__ == "__main__":
    build_benchmark_suites()
