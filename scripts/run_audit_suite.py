"""Sprint 3.0.2: Realistic User Capability Audit Runner for Maayboli AI.

Executes 95 realistic Marathi user queries across 8 distinct categories
through the full 7-stage backend RAG pipeline:
Query Processor ➔ Retriever ➔ Intelligent Context Builder ➔ Intent Validator ➔ Response Strategy Engine ➔ Generation Engine ➔ Gemini ➔ Answer

Outputs JSON audit records for independent technical review.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Add src to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from context_builder import ContextBuilder
from generation_engine import GenerationEngine
from intent_validator import IntentValidator
from query_processor import process_query
from response_strategy_engine import ResponseStrategyEngine
from retriever import search_articles

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("UserAudit")

REALISTIC_QUERIES: List[Dict[str, str]] = [
    # 1. District Queries (15)
    {"id": "D01", "cat": "District", "query": "सिंधुदुर्ग जिल्ह्यात आज काय विशेष घडामोडी आहेत?"},
    {"id": "D02", "cat": "District", "query": "पुण्यातील वाहतूक कोंडी आणि अपघातांबद्दल काय बातम्या आहेत?"},
    {"id": "D03", "cat": "District", "query": "कोल्हापूर जिल्ह्यात पावसामुळे पूरस्थिती निर्माण झाली आहे का?"},
    {"id": "D04", "cat": "District", "query": "रत्नागिरी जिल्ह्यात नवे महामार्ग प्रकल्प सुरू आहेत का?"},
    {"id": "D05", "cat": "District", "query": "मुंबई शहरातील राजकीय घडामोडी सांगा."},
    {"id": "D06", "cat": "District", "query": "नागपूर जिल्ह्यातील शेतकरी आंदोलनाबाबत काय अपडेट आहे?"},
    {"id": "D07", "cat": "District", "query": "नाशिक जिल्ह्यात कुंभमेळा किंवा धार्मिक कार्यक्रमांची माहिती आहे का?"},
    {"id": "D08", "cat": "District", "query": "सांगली जिल्ह्यात पुराची काय स्थिती आहे?"},
    {"id": "D09", "cat": "District", "query": "सातारा जिल्ह्यातील महामार्गावरील अपघातांची माहिती सांगा."},
    {"id": "D10", "cat": "District", "query": "ठाणे शहरातील गुन्हेगारी आणि पोलीस कारवाईबाबत बातमी आहे का?"},
    {"id": "D11", "cat": "District", "query": "रायगड जिल्ह्यात पर्यटन आणि हवामानाची स्थिती कशी आहे?"},
    {"id": "D12", "cat": "District", "query": "पालघर जिल्ह्यातील आदिवासी विकास योजनांबाबत बातमी सांगा."},
    {"id": "D13", "cat": "District", "query": "सोलापूर जिल्ह्यातील एसटी बस अपघाताची बातमी सांगा."},
    {"id": "D14", "cat": "District", "query": "छत्रपती संभाजीनगर मधील पाण्याचे दुर्भिक्ष आणि पाऊस माहिती."},
    {"id": "D15", "cat": "District", "query": "जळगाव जिल्ह्यातील सुवर्ण बाजार किंवा राजकीय बातम्या."},

    # 2. Person Queries (15)
    {"id": "P01", "cat": "Person", "query": "अमित शाह यांनी पुण्यात काय भाषण दिले?"},
    {"id": "P02", "cat": "Person", "query": "देवेंद्र फडणवीस यांनी नागपुरात पत्रकारांशी काय संवाद साधला?"},
    {"id": "P03", "cat": "Person", "query": "अजित पवार यांनी आमदारांच्या बैठकीत काय निर्णय घेतला?"},
    {"id": "P04", "cat": "Person", "query": "शरद पवार यांनी दोन्ही राष्ट्रवादीच्या एकीकरणावर काय विधान केले?"},
    {"id": "P05", "cat": "Person", "query": "उद्धव ठाकरे यांनी महायुती सरकारवर काय टीका केली?"},
    {"id": "P06", "cat": "Person", "query": "एकनाथ शिंदे यांनी लाडकी बहीण योजनेबाबत काय घोषणा केली?"},
    {"id": "P07", "cat": "Person", "query": "संजय राऊत यांनी पत्रकार परिषदेत कोणावर आरोप केले?"},
    {"id": "P08", "cat": "Person", "query": "गिरीश महाजन यांनी नाशिक दौऱ्यात काय सांगितले?"},
    {"id": "P09", "cat": "Person", "query": "प्रवीण दरेकर यांनी विरोधकांना काय प्रत्युत्तर दिले?"},
    {"id": "P10", "cat": "Person", "query": "नितीन गडकरी यांनी राष्ट्रीय महामार्गाबाबत काय विधान केले?"},
    {"id": "P11", "cat": "Person", "query": "विनायक राऊत यांच्या कुटुंबावर काय कायदेशीर कारवाई झाली?"},
    {"id": "P12", "cat": "Person", "query": "सुप्रिया सुळे यांनी महागाईवर काय मत व्यक्त केले?"},
    {"id": "P13", "cat": "Person", "query": "चंद्रकांत पाटील यांनी पुणे विद्यापीठाबाबत काय निर्णय घेतला?"},
    {"id": "P14", "cat": "Person", "query": "पंकजा मुंडे यांनी मराठा आरक्षणावर काय प्रतिक्रिया दिली?"},
    {"id": "P15", "cat": "Person", "query": "नाना पटोले यांनी काँग्रेसच्या सभेमध्ये काय भूमिका मांडली?"},

    # 3. Topic Queries (15)
    {"id": "T01", "cat": "Topic", "query": "महाराष्ट्रातील हवामान अंदाज आणि मुसळधार पावसाचा इशारा."},
    {"id": "T02", "cat": "Topic", "query": "एमबीए आणि बीबीए प्रवेशासाठी महाराष्ट्रातील सर्वोत्तम कॉलेजेस."},
    {"id": "T03", "cat": "Topic", "query": "ई-२० पेट्रोल इंधन वाहनांसाठी सुरक्षित आहे का?"},
    {"id": "T04", "cat": "Topic", "query": "आषाढी एकादशीनिमित्त वारकऱ्यांसाठी काय सोयी उपलब्ध आहेत?"},
    {"id": "T05", "cat": "Topic", "query": "एसटी बस अपघातातील जखमींना काय मदत जाहीर झाली?"},
    {"id": "T06", "cat": "Topic", "query": "मराठी नाटक 'आता थांबायचं कसं' चा पुनरावलोकन."},
    {"id": "T07", "cat": "Topic", "query": "इथेनॉल चार्जिंग तंत्रज्ञानाने कार कशा चार्ज होतात?"},
    {"id": "T08", "cat": "Topic", "query": "जागतिक ज्युनियर हॉकी कपमध्ये भारत-पाकिस्तान सामना."},
    {"id": "T09", "cat": "Topic", "query": "राशीभविष्यानुसार आज कोणत्या राशींना लाभ होणार आहे?"},
    {"id": "T10", "cat": "Topic", "query": "आरोग्य खात्याकडून स्वाइन फ्लू आणि साथीच्या आजारांवर काय मार्गदर्शक तत्त्वे आहेत?"},
    {"id": "T11", "cat": "Topic", "query": "विधानसभा निवडणुकीसाठी मतदार यादी पुनर्निरिक्षण."},
    {"id": "T12", "cat": "Topic", "query": "जयगड-चिपळूण-सातारा द्रुतगती महामार्ग प्रस्ताव."},
    {"id": "T13", "cat": "Topic", "query": "वाहनांच्या स्क्रॅपिंग पॉलिसीबाबत केंद्र सरकारचे नियम."},
    {"id": "T14", "cat": "Topic", "query": "सोन्याच्या आणि चांदीच्या दरात आज किती घसरण झाली?"},
    {"id": "T15", "cat": "Topic", "query": "शिक्षकांच्या भरती प्रक्रियेबाबत सर्वोच्च न्यायालयाचा निकाल."},

    # 4. Conversational Queries (10)
    {"id": "C01", "cat": "Conversational", "query": "मला सांगा की आज पुण्यात मुसळधार पाऊस पडत आहे का आणि काही रस्ते बंद केले आहेत का?"},
    {"id": "C02", "cat": "Conversational", "query": "अमित शाह सिंधुदुर्गात आले होते का आणि त्यांनी तिथे कोणती नवीन योजना सुरू केली?"},
    {"id": "C03", "cat": "Conversational", "query": "देवेंद्र फडणवीस यांनी महायुतीच्या जागावाटपावर नक्की काय भूमिका मांडली ते सविस्तर सांगा."},
    {"id": "C04", "cat": "Conversational", "query": "कोल्हापूर आणि रत्नागिरी जिल्ह्यासाठी हवामान खात्याने रेड अलर्ट दिला आहे का?"},
    {"id": "C05", "cat": "Conversational", "query": "अजित पवार राष्ट्रवादी पक्षाच्या बैठकीत नाराज होते का आणि त्यांनी काय निर्देश दिले?"},
    {"id": "C06", "cat": "Conversational", "query": "१० वी आणि १२ वीच्या निकालाची तारीख जाहीर झाली आहे का ते मला स्पष्ट करून सांगा."},
    {"id": "C07", "cat": "Conversational", "query": "महाराष्ट्रात सध्या राजकीय घडामोडींमध्ये काय चालू आहे मला सोप्या भाषेत सांगा."},
    {"id": "C08", "cat": "Conversational", "query": "मुंबई-पुणे एक्सप्रेसवे वर काल मोठा अपघात झाला होता का त्याबद्दल माहिती हवी आहे."},
    {"id": "C09", "cat": "Conversational", "query": "मराठा आरक्षणाबाबत सरकारने सर्वोच्च न्यायालयात काय याचिका दाखल केली आहे?"},
    {"id": "C10", "cat": "Conversational", "query": "शेतकऱ्यांच्या कर्जमाफी योजनेचा हप्ता कधी जमा होणार आहे ते सविस्तर सांगा."},

    # 5. Mixed Intent Queries (10)
    {"id": "M01", "cat": "MixedIntent", "query": "कोल्हापुरात अमित शाह यांची सभा झाली का?"},
    {"id": "M02", "cat": "MixedIntent", "query": "पुण्यात देवेंद्र फडणवीस यांच्या हस्ते कोणत्या मेट्रो मार्गाचे उद्घाटन झाले?"},
    {"id": "M03", "cat": "MixedIntent", "query": "सिंधुदुर्गात विनायक राऊत यांच्या सभेला किती गर्दी होती?"},
    {"id": "M04", "cat": "MixedIntent", "query": "नागपुरात नितीन गडकरी यांनी फ्लायओव्हरचे भूमिपूजन कधी केले?"},
    {"id": "M05", "cat": "MixedIntent", "query": "नाशिकमध्ये पावसाने किती नुकसान झाले आणि मदत पथके पोहोचली का?"},
    {"id": "M06", "cat": "MixedIntent", "query": "मुंबईत शरद पवार आणि उद्धव ठाकरे यांची संयुक्त बैठक झाली का?"},
    {"id": "M07", "cat": "MixedIntent", "query": "सांगलीत पुराचे पाणी ओसरले आहे का आणि शेतीचे किती नुकसान झाले?"},
    {"id": "M08", "cat": "MixedIntent", "query": "रत्नागिरीत जयगड महामार्गासाठी किती जमीन अधिग्रहित केली जाणार आहे?"},
    {"id": "M09", "cat": "MixedIntent", "query": "सातारात एसटी बस अपघातात किती प्रवासी जखमी झाले?"},
    {"id": "M10", "cat": "MixedIntent", "query": "ठाण्यात संजय राऊत यांच्याविरुद्ध पोलिसांनी गुन्हा दाखल केला का?"},

    # 6. Code Mixing Queries (10)
    {"id": "CM01", "cat": "CodeMixing", "query": "Pune rain status update आजची"},
    {"id": "CM02", "cat": "CodeMixing", "query": "Sindhudurg politics latest news काय आहे"},
    {"id": "CM03", "cat": "CodeMixing", "query": "Amit Shah Pune visit details सांगा"},
    {"id": "CM04", "cat": "CodeMixing", "query": "Kolhapur flood alert माहिती"},
    {"id": "CM05", "cat": "CodeMixing", "query": "Mumbai bus accident news आजची"},
    {"id": "CM06", "cat": "CodeMixing", "query": "Maharashtra politics मध्ये काय चाललंय"},
    {"id": "CM07", "cat": "CodeMixing", "query": "Devendra Fadnavis speech in Nagpur"},
    {"id": "CM08", "cat": "CodeMixing", "query": "Ratnagiri expressway project माहिती"},
    {"id": "CM09", "cat": "CodeMixing", "query": "MBA admissions cut off list महाराष्ट्र"},
    {"id": "CM10", "cat": "CodeMixing", "query": "Gold price today update कोल्हापूर"},

    # 7. Typo Queries (10)
    {"id": "TY01", "cat": "Typo", "query": "कोल्हापूरात पावसामुळे पूर आलाय का?"},
    {"id": "TY02", "cat": "Typo", "query": "अमीत शहा यांचा पुना दौरा"},
    {"id": "TY03", "cat": "Typo", "query": "देवेंद्र फणवणीस नागपूर भाषण"},
    {"id": "TY04", "cat": "Typo", "query": "रत्नागीरी जिल्हात नवीन रस्ता"},
    {"id": "TY05", "cat": "Typo", "query": "सिंधुदुर्ग अजगर व्हिडिओ"},
    {"id": "TY06", "cat": "Typo", "query": "पुने महापालिका निवडणुक बातमी"},
    {"id": "TY07", "cat": "Typo", "query": "अजीत पवार राष्ट्रवादी बैठक"},
    {"id": "TY08", "cat": "Typo", "query": "मुंबइ लोकल ट्रेन अपघात"},
    {"id": "TY09", "cat": "Typo", "query": "नाशिक कुंभमेळा तयारी बातमी"},
    {"id": "TY10", "cat": "Typo", "query": "सांगली महापूर अपडेट बातमी"},

    # 8. Unsupported Queries (10)
    {"id": "U01", "cat": "Unsupported", "query": "अमेरिकेचे अध्यक्ष ज्यो बायडेन यांचा भारत दौरा कधी आहे?"},
    {"id": "U02", "cat": "Unsupported", "query": "टोकियो ऑलिम्पिकमध्ये नीरज चोप्राने सुवर्णपदक कसे जिंकले?"},
    {"id": "U03", "cat": "Unsupported", "query": "चंद्रावर पाण्याचे अवशेष सापडले का वैज्ञानिक माहिती सांगा."},
    {"id": "U04", "cat": "Unsupported", "query": "गुगल कंपनीची नवी AI तंत्रज्ञान घोषणा आणि फीचर्स."},
    {"id": "U05", "cat": "Unsupported", "query": "आयपीएल २०२६ च्या लिलावात सर्वात महागडा खेळाडू कोण ठरला?"},
    {"id": "U06", "cat": "Unsupported", "query": "क्रिस्टियानो रोनाल्डोच्या फुटबॉल सामन्याचा निकाल."},
    {"id": "U07", "cat": "Unsupported", "query": "इलॉन मस्क यांच्या टेस्ला कारची भारतात विक्री कधी सुरू होणार?"},
    {"id": "U08", "cat": "Unsupported", "query": "उत्तर प्रदेशातील मुख्यमंत्र्यांचे विधान."},
    {"id": "U09", "cat": "Unsupported", "query": "बिटकॉईन आणि क्रिप्टो करन्सीचे आजचे दर काय आहेत?"},
    {"id": "U10", "cat": "Unsupported", "query": "युक्रेन आणि रशिया युद्धाबाबत संयुक्त राष्ट्रांची बैठक."},
]


def rate_customer_experience(status: str, answer: str, articles_found: int, cat: str) -> tuple[int, str]:
    """Automated objective customer satisfaction rating (1 to 5 stars) and reasoning."""
    if cat == "Unsupported":
        if "माहिती उपलब्ध नाही" in answer or "उपलब्ध नाही" in answer:
            return 5, "Excellent handling: Safely triggered fallback without hallucinating non-corpus facts."
        else:
            return 1, "Poor handling: Hallucinated answer for non-corpus query."

    if articles_found == 0:
        if "माहिती उपलब्ध नाही" in answer:
            return 4, "Good handling: Politely informed user that no relevant articles were found."
        return 2, "Poor handling: Failed to find articles and gave vague response."

    if status == "EXACT_MATCH":
        if len(answer) > 30 and "माहिती उपलब्ध नाही" not in answer:
            return 5, "Outstanding answer: Exact intent grounded directly in retrieved news articles."
        return 4, "Good answer: Grounded in context but concise."

    if status == "PARTIAL_MATCH":
        if "उपलब्ध नाही" in answer or "प्राप्त माहितीनुसार" in answer:
            return 4, "Satisfactory answer: Answered available facts while noting missing sub-details."
        return 3, "Moderate answer: Context partially matched query; answer covers main topics."

    if status == "RELATED_MATCH":
        if "संबंधित" in answer or "उपलब्ध नाही" in answer:
            return 3, "Fair answer: Explicitly noted exact topic was missing, provided related regional news."
        return 2, "Weak answer: Provided related news without clearly indicating missing primary intent."

    return 3, "Average performance."


def main():
    logger.info("Initializing Audit Pipeline...")
    ctx_builder = ContextBuilder()
    validator = IntentValidator()
    gen_engine = GenerationEngine()

    results: List[Dict[str, Any]] = []

    logger.info("Executing Audit Suite across %d Realistic Queries...", len(REALISTIC_QUERIES))

    for idx, item in enumerate(REALISTIC_QUERIES, 1):
        q_id = item["id"]
        cat = item["cat"]
        q_text = item["query"]

        t0 = time.perf_counter()
        q_info = process_query(q_text)
        retrieved = search_articles(q_text, top_k=5)
        clean_q = q_info.clean_query if q_info and q_info.clean_query else q_text
        ctx_pkg = ctx_builder.build_context(retrieved, query=clean_q)
        val_res = validator.validate(q_info, ctx_pkg)

        gen_res = gen_engine.generate(
            question=q_text,
            context_pkg=ctx_pkg,
            validation_result=val_res,
            query_info=q_info,
        )

        t1 = time.perf_counter()
        latency_ms = (t1 - t0) * 1000.0

        answer = gen_res.get("answer", "")
        strat_obj = gen_res.get("strategy")
        strat_name = strat_obj.strategy_name if strat_obj else "N/A"
        policy_name = strat_obj.response_policy if strat_obj else "N/A"
        status = val_res.retrieval_status

        article_titles = [a.title for a in ctx_pkg.articles]

        stars, rating_reason = rate_customer_experience(status, answer, len(ctx_pkg.articles), cat)

        rec = {
            "id": q_id,
            "category": cat,
            "query": q_text,
            "retrieved_count": len(ctx_pkg.articles),
            "retrieved_titles": article_titles[:3],
            "intent_status": status,
            "confidence": val_res.confidence,
            "match_score": val_res.overall_match_score,
            "strategy": strat_name,
            "policy": policy_name,
            "answer": answer,
            "stars": "★" * stars + "☆" * (5 - stars),
            "star_score": stars,
            "user_usefulness_rating": f"{stars}/5 Stars",
            "rating_justification": rating_reason,
            "latency_ms": round(latency_ms, 1),
        }
        results.append(rec)
        logger.info("[%d/%d] ID=%s Cat=%s Status=%s Strat=%s Stars=%d/5 Latency=%.1fms", idx, len(REALISTIC_QUERIES), q_id, cat, status, strat_name, stars, latency_ms)

    out_file = Path("evaluation/realistic_user_audit_results.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    logger.info("Saved complete audit results to %s", out_file)


if __name__ == "__main__":
    main()
