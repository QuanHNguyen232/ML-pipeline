import asyncio
import time
from openai import OpenAI, AsyncOpenAI

def sync_openai(prompt, client, enable_thinking):
    chat_response = client.chat.completions.create(
        model="Qwen/Qwen3-8B",
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=32768,
        temperature=0.6,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": enable_thinking},
        },
    )
    print("Chat response:", chat_response)

async def stream_openai_response(prompt, client, enable_thinking):
    print("\nChat response: ", end="")
    response = await client.chat.completions.create(
        model="Qwen/Qwen3-8B",
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=32768,
        temperature=0.6,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": enable_thinking},
        },
        stream=True,
    )
    async for chunk in response:
        if chunk.choices:
            content = chunk.choices[0].delta.content
            print(content, end="", flush=True)

    print()  # Final newline after stream ends

def main():
    prompt = "Give me a short introduction to large language models."

    # Modify OpenAI's API key and API base to use vLLM's API server.
    openai_api_key = "token-abc123"
    openai_api_base = "http://localhost:8000/v1"
    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    models_list = client.models.list()
    print(f"models_list={models_list}")

    # sync_openai(prompt, client, True)

    # Run the asynchronous function
    async_client = AsyncOpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    asyncio.run(stream_openai_response(prompt, async_client, False))
    

if __name__ == "__main__":
    main()