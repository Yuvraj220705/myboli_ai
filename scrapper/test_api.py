import requests

url = "http://127.0.0.1:5000/chat"

response = requests.post(
    url,
    json={
    "question": "२० जुलैला काय घडलं?"
}
)

print(response.status_code)
print(response.json())