import json
import requests

url = "http://127.0.0.1:5000/chatbot/ask"

queries = [
    # "अमित शाह यांच्या दौऱ्याबद्दल काय बातमी आहे?",
    # "नागपूर अपघातात काय घडलं?",
    # "राजकारण",
    # "विनायक राऊत",
    # "आजच्या प्रमुख बातम्या सांग. विशेषतः अमित शाह यांच्या पुणे दौऱ्याबद्दल काय घडलं, नागपूरमधील अपघाताची माहिती काय आहे, विनायक राऊत प्रकरणात नवीन काय घडामोडी आहेत आणि राज्यातील राजकीय वातावरणावर त्याचा काही परिणाम झाला आहे का?",
    # "OpenAI",
    # "NASA",
    "अमीत शाह",
]

print("=" * 70)
print("  MYBOLI AI — END-TO-END RAG API EVALUATION SUITE")
print("=" * 70)

for i, q in enumerate(queries, 1):
    payload = {
        "question": q,
        "session_id": f"test_session_{i}",
    }

    try:
        response = requests.post(url, json=payload)
        status = response.status_code

        print(f"\n[{i}/{len(queries)}] Query: '{q}'")
        print(f"Status Code: {status}")

        if status == 200:
            data = response.json()
            answer = data.get("answer", "")
            sources = data.get("sources", [])
            print(f"Sources   : {sources}")
            print(f"Answer    :\n{answer}")
        else:
            print(f"Error Response: {response.text}")

    except Exception as e:
        print(f"Request failed for query '{q}': {e}")

    print("-" * 70)
