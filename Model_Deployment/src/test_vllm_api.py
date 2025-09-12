import requests
import json


# API_URL = "http://localhost:8000/"  # Default vLLM OpenAI-compatible endpoint
API_URL = "http://91.134.104.232:8000/" # http://<vllm-server-external-ip>:8000

headers = {
    "Content-Type": "application/json"
}

data = {
    "model": "facebook/opt-125m",
    # "messages": [
    #     {"role": "user", "content": "Give me a short introduction to large language models."}
    # ],
    "prompt": "San Francisco is a",
    "temperature": 0.6,
    # "top_p": 0.95,
    "max_tokens": 1024
}

def check_health():
    response = requests.get(f"{API_URL}/ping")
    if response.status_code == 200:
        print("Health check passed")
    else:
        print(f"Health check failed with status code {response.status_code}")
        print(response.text)

def main():
    response = requests.post(API_URL + "v1/completions", headers=headers, data=json.dumps(data))

    if response.status_code == 200:
        result = response.json()
        # print("Response:")
        # print(json.dumps(result, indent=2, ensure_ascii=False))
        return result
    else:
        print(f"Request failed with status code {response.status_code}")
        return response.text

if __name__ == "__main__":
    print(API_URL)
    check_health()
    output = [main() for _ in range(1000)]
    # print(output)