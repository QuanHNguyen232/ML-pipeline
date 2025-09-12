# Deployment

## (Optional) Download model
1.  **Go to hf_download dir**
    ```bash
    cd hf_download
    ```
1.  **Change model name and download**
    ```bash
    # Change model name in main.py
    uv run main.py
    ```
    This will create dir `models_local/` if not exists and save model there. Can be used for Ray Serve or vLLM.

## vLLM

## Ray Serve