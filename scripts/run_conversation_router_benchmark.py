"""Sprint 5.0.1: Automated Benchmark Evaluation for Conversation Router & User Interaction Layer.

Evaluates 50 Conversational Inputs vs 50 Genuine News Queries against ConversationRouter.
Generates evaluation/conversation_router_results.json with metrics:
- Classification Accuracy
- Precision, Recall, F1-Score
- False Positives (News Queries routed as Conversational)
- False Negatives (Conversational Inputs routed as News Queries)
- Average Latency (ms)
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Ensure src/ is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from conversation_router import ConversationRouter

CONVERSATIONAL_INPUTS: List[str] = [
    # Greetings
    "Hi", "Hello", "Hey", "hii", "हाय", "नमस्कार", "नमस्ते", "Good Morning", "Good Evening", "Good Afternoon",
    # Gratitude
    "Thanks", "Thank you", "धन्यवाद", "खूप धन्यवाद", "Thank you so much", "thx", "थँक्यू", "थँक्स", "खूप मनापासून धन्यवाद", "thanks a lot",
    # Farewell
    "Bye", "Goodbye", "See you", "बाय", "निघतो", "पुन्हा भेटू", "बाय बाय", "शुभ रात्री", "cya", "bye bye",
    # Identity
    "Who are you?", "तू कोण आहेस?", "Who made you?", "तुझे नाव काय आहे?", "who created you", "who developed you", "what is your name",
    # Capability
    "What can you do?", "तू काय करू शकतोस?", "Which news do you provide?", "what news do you have", "तू काय काय करू शकतोस",
    # Help
    "Help", "मदत", "तुझी मदत कशी मिळेल?", "How can you help?", "मदत करा", "मला मदत हवी आहे"
]

NEWS_QUERIES: List[str] = [
    "पुण्यात आज पावसाची काय स्थिती आहे?",
    "सिंधुदुर्ग जिल्ह्यात पर्यटन वाढीसाठी कोणते नवीन प्रकल्प सुरू झाले?",
    "कोल्हापूर जिल्ह्यातील पूर परिस्थिती अपडेट सांगा",
    "अमित शाह यांनी नागपूर दौऱ्यात काय घोषणा केल्या?",
    "देवेंद्र फडणवीस आणि एकनाथ शिंदे यांची वर्षा बंगल्यावर बैठक",
    "शरद पवार यांनी बारामतीत पत्रकारांशी काय संवाद साधला?",
    "उद्धव ठाकरे यांची मुंबईतील शिवसेना भवन येथे सभा",
    "नितीन गडकरी यांनी समृद्धी महामार्गाबद्दल काय विधान केले?",
    "संजय राऊत यांची आजची पत्रकार परिषद काय होती?",
    "रत्नागिरी जिल्ह्यात काजू बागायतदारांसाठी नवीन योजना",
    "नाशिकमध्ये कुंभमेळा नियोजनाबाबत जिल्हाधिकाऱ्यांची बैठक",
    "महाराष्ट्रातील पुढील ४८ तासांचा हवामान अंदाज",
    "पुण्यातील मेट्रो विस्ताराबाबत महापालिकेचा निर्णय",
    "मुंबई-पुणे एक्सप्रेसवे वरील वाहतूक कोंडी बद्दल बातमी",
    "महाराष्ट्रातील शाळांना दिवाळी सुट्टीचे वेळापत्रक",
    "सोलापूर जिल्ह्यात शेतकरी आंदोलनाची सद्यस्थिती",
    "सातारा जिल्ह्यात बाजरी पिकाचे नुकसान",
    "सांगली शहर पाणी पुरवठा योजना अपडेट",
    "ठाणे जिल्ह्यात नवीन उड्डाणपुलाचे उद्घाटन",
    "पालघर जिल्ह्यात आरोग्य सेवा बळकटीकरणासाठी निधी",
    "रायगड जिल्ह्यातील किल्ल्यांच्या संवर्धनासाठी घोषणा",
    "जळगाव जिल्ह्यात केळी उत्पादकांसाठी अनुदान",
    "धुळे जिल्ह्यात पोलीस भरती प्रक्रिया",
    "नंदुरबार जिल्ह्यातील आदिवासी विकास प्रकल्प",
    "जाडगाव जालना रेल्वे मार्ग अपडेट",
    "बीड जिल्ह्यातील दुष्काळ पाहणी दौरा",
    "लातूर शहरात नवीन वैद्यकीय महाविद्यालय",
    "धाराशिव जिल्ह्यातील तुळजापूर मंदिर विकास आराखडा",
    "नांदेड जिल्ह्यात गुरुद्वारा परिसरात सुरक्षा व्यवस्था",
    "परभणी कृषी विद्यापीठाचा नवीन संशोधन प्रकल्प",
    "हिंगोली जिल्ह्यात हळद उत्पादनाला चालना",
    "अमरावती जिल्ह्यात नवीन औद्योगिक वसाहत",
    "अकोला शहरात रस्ते रुंदीकरण मोहीम",
    "वाशीम जिल्ह्यात सोयाबीन खरेदी केंद्र",
    "बुलढाणा जिल्ह्यात सिंचन प्रकल्पाचे काम वेगाने",
    "यवतमाळ जिल्ह्यात कापूस दराबाबत शेतकरी चिंताग्रस्त",
    "वर्धा जिल्ह्यात महात्मा गांधी सेवा आश्रम उपक्रम",
    "भंडारा जिल्ह्यात धान खरेदी प्रक्रिया सुरू",
    "गोंदिया जिल्ह्यात वन्यजीव संरक्षणासाठी उपाययोजना",
    "चंद्रपूर जिल्ह्यात औष्णिक वीज केंद्र प्रकल्प",
    "गडचिरोली जिल्ह्यात नक्षलविरोधी अभियान",
    "महाराष्ट्रातील यंदाचा मान्सून पाऊस कसा राहील?",
    "विधानसभा निवडणुकीच्या पार्श्वभूमीवर राजकीय घडामोडी",
    "महाराष्ट्रात एसटी बस प्रवाशांसाठी नवीन सवलती",
    "कोल्हापुरी चप्पल उद्योगाला प्रोत्साहन देणारा निर्णय",
    "सिंधुदुर्गातील चिपी विमानतळ उड्डाण वेळापत्रक",
    "आज महाराष्ट्रातील ताज्या मुख्य बातम्या कोणत्या?",
    "पुणे विद्यापीठाच्या परीक्षांचे वेळापत्रक जाहीर",
    "मुंबईत लोकल ट्रेन सेवा विस्कळीत",
    "महाराष्ट्रातील मराठा आरक्षण आंदोलनाची बातमी"
]


def run_benchmark() -> Dict[str, Any]:
    """Execute benchmark over 50 conversational inputs and 50 genuine news queries."""
    print("=" * 70)
    print("  CONVERSATION ROUTER BENCHMARK EVALUATION (Sprint 5.0.1)")
    print("=" * 70)

    router = ConversationRouter()

    true_conversational = 0  # Conversational inputs correctly routed away from RAG
    false_news_queries = 0   # Conversational inputs mistakenly sent to RAG
    true_news_queries = 0    # News queries correctly sent to RAG
    false_conversational = 0 # News queries mistakenly intercepted as Conversational

    detailed_results = []
    latencies = []

    # 1. Evaluate Conversational Inputs
    for msg in CONVERSATIONAL_INPUTS:
        t0 = time.perf_counter()
        res = router.route_message(msg)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        if not res.should_use_rag:
            true_conversational += 1
            status = "TRUE_CONVERSATIONAL"
        else:
            false_news_queries += 1
            status = "FALSE_NEWS_QUERY"

        detailed_results.append({
            "message": msg,
            "category": "CONVERSATIONAL",
            "detected_intent": res.intent_type,
            "should_use_rag": res.should_use_rag,
            "status": status,
            "latency_ms": round(dt, 4),
        })

    # 2. Evaluate Genuine News Queries
    for q in NEWS_QUERIES:
        t0 = time.perf_counter()
        res = router.route_message(q)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        if res.should_use_rag:
            true_news_queries += 1
            status = "TRUE_NEWS_QUERY"
        else:
            false_conversational += 1
            status = "FALSE_CONVERSATIONAL"

        detailed_results.append({
            "message": q,
            "category": "NEWS_QUERY",
            "detected_intent": res.intent_type,
            "should_use_rag": res.should_use_rag,
            "status": status,
            "latency_ms": round(dt, 4),
        })

    total_inputs = len(CONVERSATIONAL_INPUTS) + len(NEWS_QUERIES)
    accuracy = round(((true_conversational + true_news_queries) / total_inputs) * 100.0, 2)
    precision = round((true_conversational / (true_conversational + false_conversational)) * 100.0, 2) if (true_conversational + false_conversational) > 0 else 0.0
    recall = round((true_conversational / (true_conversational + false_news_queries)) * 100.0, 2) if (true_conversational + false_news_queries) > 0 else 0.0
    f1_score = round(2 * (precision * recall) / (precision + recall), 2) if (precision + recall) > 0 else 0.0
    avg_latency = round(sum(latencies) / len(latencies), 4)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_conversational_inputs": len(CONVERSATIONAL_INPUTS),
        "total_news_queries": len(NEWS_QUERIES),
        "correctly_routed_conversational": true_conversational,
        "correctly_routed_news_queries": true_news_queries,
        "false_positives_news_as_conversational": false_conversational,
        "false_negatives_conversational_as_news": false_news_queries,
        "classification_accuracy_pct": accuracy,
        "precision_pct": precision,
        "recall_pct": recall,
        "f1_score": f1_score,
        "average_latency_ms": avg_latency,
        "detailed_results": detailed_results,
    }

    out_path = PROJECT_ROOT / "evaluation" / "conversation_router_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Conversational Inputs Tested: {len(CONVERSATIONAL_INPUTS)}")
    print(f"News Queries Tested        : {len(NEWS_QUERIES)}")
    print("-" * 50)
    print(f"Correctly Routed Conversational : {true_conversational} / {len(CONVERSATIONAL_INPUTS)}")
    print(f"Correctly Routed News Queries   : {true_news_queries} / {len(NEWS_QUERIES)}")
    print(f"False Positives (News -> Conv)  : {false_conversational}")
    print(f"False Negatives (Conv -> News)  : {false_news_queries}")
    print("-" * 50)
    print(f"Classification Accuracy : {accuracy}%")
    print(f"Precision               : {precision}%")
    print(f"Recall                  : {recall}%")
    print(f"F1 Score                : {f1_score}")
    print(f"Avg Routing Latency     : {avg_latency} ms (Target < 0.1 ms)")
    print(f"\nSaved benchmark results to {out_path}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    run_benchmark()
