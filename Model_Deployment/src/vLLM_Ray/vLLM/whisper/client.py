import asyncio
import time
from openai import OpenAI, AsyncOpenAI
from vllm.assets.audio import AudioAsset

import librosa

def sync_openai(audio_path: str, client: OpenAI):
    """
    Perform synchronous transcription using OpenAI-compatible API.
    """
    with open(audio_path, "rb") as f:
        start = time.time()

        transcription = client.audio.transcriptions.create(
            file=f,
            model="openai/whisper-large-v3",
            language="en",
            response_format="json",
            temperature=0.0,
            # Additional sampling params not provided by OpenAI API.
            extra_body=dict(
                seed=4419,
                repetition_penalty=1.3,
            ),
        )
        duration = time.time() - start

        print("transcription result:", transcription.text)
        print(f"Duration: {duration} seconds")


async def stream_openai_response(audio_path: str, client: AsyncOpenAI):
    """
    Perform asynchronous transcription using OpenAI-compatible API.
    """
    print("\ntranscription result:", end=" ")
    with open(audio_path, "rb") as f:
        transcription = await client.audio.transcriptions.create(
            file=f,
            model="openai/whisper-large-v3",
            language="en",
            response_format="json",
            temperature=0.0,
            # Additional sampling params not provided by OpenAI API.
            extra_body=dict(
                seed=420,
                top_p=0.6,
            ),
            stream=True,
        )
        async for chunk in transcription:
            if chunk.choices:
                content = chunk.choices[0].get("delta", {}).get("content")
                print(content, end="", flush=True)

    print()  # Final newline after stream ends


def main():
    mary_had_lamb = str(AudioAsset("mary_had_lamb").get_local_path())
    winning_call = str(AudioAsset("winning_call").get_local_path())

    # Modify OpenAI's API key and API base to use vLLM's API server.
    openai_api_key = "token-abc123"
    openai_api_base = "http://localhost:8000/v1"
    client = OpenAI(
        api_key=openai_api_key,
        base_url=openai_api_base,
    )

    sync_openai(benchmark_audio, client)

    # Run the asynchronous function
    # async_client = AsyncOpenAI(
    #     api_key=openai_api_key,
    #     base_url=openai_api_base,
    # )
    # asyncio.run(stream_openai_response(winning_call, async_client))
    

if __name__ == "__main__":
    main()