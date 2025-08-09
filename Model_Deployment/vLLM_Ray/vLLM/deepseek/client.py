import asyncio
import time
from openai import OpenAI, AsyncOpenAI
# https://docs.vllm.ai/en/latest/examples/online_serving/openai_chat_completion_with_reasoning.html

def sync_openai(model, prompt, client, enable_thinking):
    chat_response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=32768,
        temperature=0.6,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            "chat_template_kwargs": {"thinking": enable_thinking},
        },
    )
    print("Chat response:", chat_response)

async def stream_openai_response(model, prompt, client, enable_thinking):
    # https://docs.vllm.ai/en/latest/examples/online_serving/openai_chat_completion_with_reasoning_streaming.html
    print("\nChat response:")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": prompt},
        ],
        max_tokens=32768,
        temperature=0.6,
        top_p=0.95,
        presence_penalty=1.5,
        extra_body={
            # "top_k": 20,
            "chat_template_kwargs": {"enable_thinking": enable_thinking},
        },
        stream=True,
    )
    printed_reasoning_content = False
    printed_content = False
    async for chunk in response:
        # if chunk.choices:
        #     content = chunk.choices[0].delta.content
        #     print(content, end="", flush=True)
        reasoning_content = (
            getattr(chunk.choices[0].delta, "reasoning_content", None) or None
        )
        content = getattr(chunk.choices[0].delta, "content", None) or None

        if reasoning_content is not None:
            if not printed_reasoning_content:
                printed_reasoning_content = True
                print("reasoning_content:", end="", flush=True)
            print(reasoning_content, end="", flush=True)
        elif content is not None:
            if not printed_content:
                printed_content = True
                print("\ncontent:", end="", flush=True)
            # Extract and print the content
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
    model = models_list.data[0].id
    print(f"models_list={models_list}")
    print(f"model=[{model}]")

    # sync_openai(model, prompt, client, True)

    # Run the asynchronous function
    async_client = AsyncOpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )
    asyncio.run(stream_openai_response(model, prompt, async_client, False))
    

if __name__ == "__main__":
    main()