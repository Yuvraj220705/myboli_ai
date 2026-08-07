"""Sprint 4.0.0: Automated Benchmark Runner for Unknown Entity Guardrail.

Evaluates 50 Supported Queries vs 50 Unsupported Queries against UnknownEntityGuard.
Generates evaluation/unknown_entity_guard_results.json with metrics:
- Blocked Correctly (True Positives)
- Passed Correctly (True Negatives)
- False Positives (Supported blocked by mistake)
- False Negatives (Unsupported allowed by mistake)
- Precision, Recall, Accuracy, F1-Score, Average Latency (ms)
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

from entity_normalizer import DistrictNormalizer, PersonNormalizer, WordNormalizer
from unknown_entity_guard import UnknownEntityGuard

SUPPORTED_QUERIES: List[str] = [
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
    "महाराष्ट्रातील मराठा आरक्षण आंदोलनाची बातमी",
]

UNSUPPORTED_QUERIES: List[str] = [
    "अमेरिकेचे अध्यक्ष जो बायडेन भारतात कधी येणार?",
    "डोनाल्ड ट्रम्प यांच्या निवडणुकीतील भाषणावर अमेरिकेत काय प्रतिक्रिया आली?",
    "युक्रेन आणि रशिया युद्धाबाबत संयुक्त राष्ट्रांची आणीबाणी बैठक",
    "क्रिस्टियानो रोनाल्डोच्या फुटबॉल सामन्याचा निकाल सांगा",
    "इलॉन मस्क यांच्या टेस्ला कारची भारतात विक्री कधी सुरू होणार?",
    "गूगल कंपनीची नवी Gemini AI तंत्रज्ञान घोषणा",
    "ओपनएआय कडून ChatGPT 5 चे फीचर्स",
    "ॲपल व्हिजन प्रो ची किंमत आणि फीचर्स सांगा",
    "आयपीएल २०२६ च्या लिलावात सर्वात महागडा खेळाडू कोण?",
    "बिटकॉइन आणि क्रिप्टो करन्सीचे आजचे जागतिक दर काय आहेत?",
    "कमला हॅरिस यांच्या निवडणुकीतील प्रचाराची बातमी",
    "व्लादिमीर पुतिन यांचा मॉस्को येथील विशेष संदेश",
    "व्होलोडिमिर झेलेंस्की यांची वॉशिंग्टन भेट",
    "ऋषी सुनक यांनी ब्रिटन संसदेत काय भाषण दिले?",
    "इमॅन्युएल मॅक्रॉन यांचा पॅरिस येथील कार्यक्रम",
    "बेंजामिन नेतान्याहू यांनी इस्रायल सैन्याला काय आदेश दिले?",
    "जस्टिन ट्रुडो यांनी कॅनडा संसदेत दिलेले स्पष्टीकरण",
    "शी जिनपिंग यांच्या चीनमधील आर्थिक धोरणांबद्दल बातमी",
    "टोकियो ऑलिम्पिकमध्ये नीरज चोप्राने सुवर्णपदक कसे जिंकले?",
    "लिओनेल मेस्सीच्या इंटर मियामी संघाचा सामना निकाल",
    "फीफा वर्ल्ड कप २०२६ चे यजमान देश कोणते आहेत?",
    "ऑस्कर अवॉर्ड्स २०२६ चे विजेते कोण ठरले?",
    "ग्रॅमी अवॉर्ड्स २०२६ मधील सर्वोत्कृष्ट गाणे",
    "सुपर बाऊल फायनलचा निकाल काय लागला?",
    "विम्बल्डन टेनिस स्पर्धेतील अंतिम सामना निकाल",
    "फॉर्म्युला १ कार रेस मध्ये ल्युईस हॅमिल्टनचा विजय",
    "एनबीए बास्केटबॉल फायनल चॅम्पियन कोण?",
    "युएफसी मिक्स्ड मार्शल आर्ट्स चॅम्पियनशिप बातमी",
    "इथेरियम क्रिप्टो गॅस फी अपडेट्स",
    "फेडरल रिझर्व्ह कडून अमेरिकेत व्याजदर कपात घोषणा",
    "वॉल स्ट्रीट शेअर बाजारात मोठी घसरण",
    "जागतिक बाजारात कच्च्या तेलाचे आजचे दर",
    "नासाच्या आर्टेमिस मून मिशन बद्दल माहिती",
    "स्टारलिंक सॅटेलाइट इंटरनेट सेवा भारतात कधी येणार?",
    "स्पेसएक्स स्टारशिप रॉकेटचे यशस्वी उड्डाण",
    "एनव्हिडिया च्या AI चिप्स ची बाजारातील मागणी",
    "मायक्रोसॉफ्ट विंडोज ११ चा नवीन अपडेट",
    "अ‍ॅमेझॉन एडब्ल्यूएस क्लाउड सर्व्हर डाऊन बातमी",
    "मेटा थ्रेड्स ॲपचे नवीन प्रायव्हसी अपडेट",
    "सॅमसंग गॅलक्सी S26 अल्ट्रा ची किंमत किती?",
    "सोनी प्लेस्टेशन ६ ची अधिकृत रिलीज डेट",
    "युरोपियन युनियन कडून टेक कंपन्यांना दंड",
    "नाटो सैन्याची पूर्व युरोपमध्ये तैनाती",
    "सोन्याचे आंतरराष्ट्रीय बाजारातील दर आज काय आहेत?",
    "डब्ल्यूएचओ कडून नवीन साथीच्या रोगाबाबत इशारा",
    "जी२० शिखर परिषदेचे पुढील अध्यक्षपद कोणाकडे?",
    "अँटार्टिका मधील हिमनग वितळण्याबाबत वैज्ञानिकांचा इशारा",
    "दुबई आंतरराष्ट्रीय विमानतळावर पूरस्थिती",
    "सिडनी ऑपेरा हाऊस येथील सांस्कृतिक महोत्सव",
    "लंडनमध्ये अंडरग्राउंड ट्रेन संप",
]


def run_benchmark() -> Dict[str, Any]:
    """Execute benchmark over 50 supported and 50 unsupported queries."""
    print("=" * 70)
    print("  UNKNOWN ENTITY GUARD BENCHMARK EVALUATION (Sprint 4.0.0)")
    print("=" * 70)

    guard = UnknownEntityGuard()

    true_negatives = 0  # Supported passed
    false_positives = 0  # Supported incorrectly blocked
    true_positives = 0   # Unsupported blocked
    false_negatives = 0  # Unsupported incorrectly passed

    detailed_results = []
    latencies = []

    # 1. Evaluate Supported Queries
    for q in SUPPORTED_QUERIES:
        t0 = time.perf_counter()
        res = guard.inspect_query(q)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        if res.should_block:
            false_positives += 1
            status = "FALSE_POSITIVE"
        else:
            true_negatives += 1
            status = "TRUE_NEGATIVE"

        detailed_results.append({
            "query": q,
            "category": "SUPPORTED",
            "should_block": res.should_block,
            "status": status,
            "reason": res.reason,
            "latency_ms": round(dt, 4),
        })

    # 2. Evaluate Unsupported Queries
    for q in UNSUPPORTED_QUERIES:
        t0 = time.perf_counter()
        res = guard.inspect_query(q)
        dt = (time.perf_counter() - t0) * 1000.0
        latencies.append(dt)

        if res.should_block:
            true_positives += 1
            status = "TRUE_POSITIVE"
        else:
            false_negatives += 1
            status = "FALSE_NEGATIVE"

        detailed_results.append({
            "query": q,
            "category": "UNSUPPORTED",
            "should_block": res.should_block,
            "status": status,
            "reason": res.reason,
            "latency_ms": round(dt, 4),
        })

    total_queries = len(SUPPORTED_QUERIES) + len(UNSUPPORTED_QUERIES)
    accuracy = round(((true_positives + true_negatives) / total_queries) * 100.0, 2)
    precision = round((true_positives / (true_positives + false_positives)) * 100.0, 2) if (true_positives + false_positives) > 0 else 0.0
    recall = round((true_positives / (true_positives + false_negatives)) * 100.0, 2) if (true_positives + false_negatives) > 0 else 0.0
    f1_score = round(2 * (precision * recall) / (precision + recall), 2) if (precision + recall) > 0 else 0.0
    avg_latency = round(sum(latencies) / len(latencies), 4)

    summary = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_supported_queries": len(SUPPORTED_QUERIES),
        "total_unsupported_queries": len(UNSUPPORTED_QUERIES),
        "blocked_correctly_tp": true_positives,
        "passed_correctly_tn": true_negatives,
        "false_positives_fp": false_positives,
        "false_negatives_fn": false_negatives,
        "accuracy_pct": accuracy,
        "precision_pct": precision,
        "recall_pct": recall,
        "f1_score": f1_score,
        "average_latency_ms": avg_latency,
        "detailed_results": detailed_results,
    }

    out_path = PROJECT_ROOT / "evaluation" / "unknown_entity_guard_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"Supported Queries Checked: {len(SUPPORTED_QUERIES)}")
    print(f"Unsupported Queries Checked: {len(UNSUPPORTED_QUERIES)}")
    print("-" * 50)
    print(f"Blocked Correctly (TP): {true_positives} / {len(UNSUPPORTED_QUERIES)}")
    print(f"Passed Correctly (TN) : {true_negatives} / {len(SUPPORTED_QUERIES)}")
    print(f"False Positives (FP)  : {false_positives}")
    print(f"False Negatives (FN)  : {false_negatives}")
    print("-" * 50)
    print(f"Accuracy  : {accuracy}%")
    print(f"Precision : {precision}%")
    print(f"Recall    : {recall}%")
    print(f"F1 Score  : {f1_score}")
    print(f"Avg Latency: {avg_latency} ms")
    print(f"\nSaved benchmark results to {out_path}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    run_benchmark()
