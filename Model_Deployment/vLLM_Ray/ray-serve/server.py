# https://github.com/vllm-project/vllm/blob/main/examples/online_serving/ray_serve_deepseek.py
# https://docs.ray.io/en/latest/serve/llm/serving-llms.html
import ray
from ray import serve
from ray.serve.llm import LLMConfig, build_openai_app

ray.init()
print(ray.cluster_resources())

llm_config = LLMConfig(
    model_loading_config={
        "model_id": "qwen-0.5b",
        # Pre-downloading the model to local storage is recommended since
        # the model is large. Set model_source="/path/to/the/model".
        "model_source": "Qwen/Qwen2.5-0.5B-Instruct",
    },
    deployment_config={
        "autoscaling_config": {
            "min_replicas": 1,
            "max_replicas": 1,
        }
    },
    # Set to the node's accelerator type.
    accelerator_type="A100", # https://docs.ray.io/en/latest/ray-core/accelerator-types.html#accelerator-types
    runtime_env={"env_vars": {"VLLM_USE_V1": "1"}},
    # Customize engine arguments as required (for example, vLLM engine kwargs).
    engine_kwargs={
        "tensor_parallel_size": 1, # requires 1 A100 GPU(s)
        # "pipeline_parallel_size": 2,
        # "gpu_memory_utilization": 0.92,
        # "dtype": "auto",
        # "max_num_seqs": 40,
        # "max_model_len": 16384,
        # "enable_chunked_prefill": True,
        # "enable_prefix_caching": True,
        # "trust_remote_code": True,
    },
)

# Deploy the application.
llm_app = build_openai_app({"llm_configs": [llm_config]})
serve.run(llm_app, blocking=True)