import requests
import json

API_URL = "http://localhost:8000/v1/completions"  # Default vLLM OpenAI-compatible endpoint

headers = {
    "Content-Type": "application/json"
}

data = {
    "model": "Qwen/Qwen3-0.6B",
    "messages": [
        {"role": "user", "content": "Give me a short introduction to large language models."}
    ],
    "temperature": 0.6,
    "top_p": 0.95,
    "max_tokens": 256
}

response = requests.post(API_URL, headers=headers, data=json.dumps(data))

if response.status_code == 200:
    result = response.json()
    print("Response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
else:
    print(f"Request failed with status code {response.status_code}")
    print(response.text) 