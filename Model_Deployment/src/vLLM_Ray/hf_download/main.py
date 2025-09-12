import os
from huggingface_hub import snapshot_download

model_name = "Qwen/Qwen2.5-0.5B-Instruct"


local_dir = f'../models_local/{model_name}'
os.makedirs(local_dir, exist_ok=True)
snapshot_download(model_name, local_dir=local_dir)


print(f"Saved model {model_name} to {local_dir}")