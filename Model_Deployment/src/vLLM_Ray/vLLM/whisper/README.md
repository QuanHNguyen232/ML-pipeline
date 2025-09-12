# Whisper vLLM

## Install
1.  **Install audio for vllm**
    ```bash
    uv add vllm[audio]
    ```
    
## Online
1.  **Deploy**
    ```bash
    vllm serve openai/whisper-large-v3 \
    --dtype auto \
    --api-key token-abc123
    ```
1.  **Run inference**
    ```bash
    uv run client.py
    ```

## Offline
1.  **Run inference**
    ```bash
    uv run offline.py
    ```