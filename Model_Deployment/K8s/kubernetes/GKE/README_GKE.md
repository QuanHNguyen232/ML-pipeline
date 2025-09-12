https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-llama-gpus-vllm#llama-4-maverick-17b-128e

USING NVIDIA-L4
https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm#autopilot

https://cloud.google.com/compute/docs/gpus/gpu-regions-zones

Request GPU in GKE: https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus

## Next steps:
- [X] Deploy Qwen3-32b (using 2 A100-40GB GPUs). Since it's too large, we must set `--max-model-len=8000`
- [ ] Expose deployment[feedbackExposing applications using services](https://cloud.google.com/kubernetes-engine/docs/how-to/exposing-apps)
- [ ] Add monitoring
- [ ] Optimizing (use TPU):
    - https://www.aleksagordic.com/blog/vllm
    - https://docs.vllm.ai/en/latest/getting_started/installation/aws_neuron.html
    - https://docs.vllm.ai/en/stable/getting_started/installation/aws_neuron.html
    - https://huggingface.co/docs/optimum-neuron/training_tutorials/qwen3-fine-tuning
    - https://aws.amazon.com/blogs/machine-learning/how-to-run-qwen-2-5-on-aws-ai-chips-using-hugging-face-libraries/
    - neu dung GCP thi co TPU: https://docs.vllm.ai/en/stable/getting_started/installation/google_tpu.html

## Enable "Google Kubernetes Engine API"
https://cloud.google.com/kubernetes-engine/docs/how-to/consuming-reservations#before_you_begin

## GPU types
https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus
Replace GPU_TYPE with the type of GPU in your target nodes. This can be one of the following:

`nvidia-b200`: NVIDIA B200 (180GB)
`nvidia-h200-141gb`: NVIDIA H200 (141GB)
`nvidia-h100-mega-80gb`: NVIDIA H100 Mega (80GB)
`nvidia-h100-80gb`: NVIDIA H100 (80GB)
`nvidia-a100-80gb`: NVIDIA A100 (80GB)
`nvidia-tesla-a100`: NVIDIA A100 (40GB)
`nvidia-l4`: NVIDIA L4
`nvidia-tesla-t4`: NVIDIA T4

## Model Size Resource Requirements

| Model Size Range | System RAM (requests) | System RAM (limits) | PVC Storage | Recommended GPU | Examples |
|------------------|----------------------|---------------------|-------------|-----------------|----------|
| **≤5GB** | 4-6GB | 8-12GB | 20-30GB | nvidia-l4, nvidia-tesla-t4 | Gemma-2B, Phi-3-mini, Qwen2-1.5B |
| **5-10GB** | 6-10GB | 12-20GB | 30-50GB | nvidia-l4, nvidia-tesla-a100 | Gemma-7B, Llama-3.1-8B, Mistral-7B |
| **10-20GB** | 10-16GB | 20-32GB | 50-80GB | nvidia-tesla-a100, nvidia-a100-80gb | Llama-3.1-70B (quantized), Qwen2.5-32B |
| **20-30GB** | 16-24GB | 32-48GB | 80-120GB | nvidia-a100-80gb, nvidia-h100-80gb | Llama-3.1-70B, Mixtral-8x7B |
| **30-50GB** | 24-32GB | 48-64GB | 120-200GB | nvidia-h100-80gb, nvidia-h100-mega-80gb | Qwen2.5-72B, Llama-3.1-405B (quantized) |
| **50-70GB** | 32-48GB | 64-96GB | 200-300GB | nvidia-h100-mega-80gb, nvidia-h200-141gb | Large quantized models, Mixtral-8x22B |

### Resource Guidelines:
- **System RAM**: Used for model loading, CPU computations, and vLLM framework overhead
- **PVC Storage**: Used for persistent model cache, avoiding re-downloads on pod restarts
- **GPU Memory**: Should be 1.5-2x the model size for optimal performance
- **Shared Memory (dshm)**: 2-8GB depending on model size and tensor parallel configuration

### Notes:
- For models >70GB, consider using tensor parallelism across multiple GPUs
- Quantized models (4-bit, 8-bit) require significantly less GPU memory
- Add 20-30% buffer to PVC storage for model updates and temporary files
- Monitor actual usage and adjust resources based on workload patterns

## Prepare environment
```bash
gcloud config set project venerian
gcloud config set billing/quota_project venerian
export PROJECT_ID=$(gcloud config get project)
export REGION=us-central1
export ZONE=us-central1-a
export CONTROL_PLANE_LOCATION=us-central1
export CLUSTER_NAME=venera-test
export VLLM_LOGGING_LEVEL=DEBUG
export NAMESPACE=llm
```

## Create a GKE cluster and node pool
1. Autopilot (recommend)
Ref: https://cloud.google.com/sdk/gcloud/reference/container/clusters/create
```bash
gcloud container clusters create-auto $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --location=$CONTROL_PLANE_LOCATION \
    --release-channel=rapid
```

2. Standard:
```bash
gcloud container clusters create $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --machine-type g2-standard-8 \
    --accelerator type=nvidia-l4,count=1 \
    --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
```

## Connect to cluster
```bash
gcloud container clusters get-credentials $CLUSTER_NAME \
    --location=$REGION
```

## Create namespace
```bash
kubectl create namespace "$NAMESPACE" || true

# Optionally set the default namespace for this context
kubectl config set-context --current --namespace="$NAMESPACE"
```

## Checking info
```bash
# Verify context
kubectl config current-context

# Quick check: is this an Autopilot cluster? Expect: true for Autopilot
gcloud container clusters describe $CLUSTER_NAME --region $REGION --format='value(autopilot.enabled)'

# Check GPU
# Should see no GPU now as there's no namespace using GPU
kubectl get nodes -o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu

# Get all namespaces:
kubectl get namespaces
```

## Create a Kubernetes secret for Hugging Face credentials
```bash
kubectl -n "$NAMESPACE" create secret generic hf-secret \
    --from-literal=hf_api_token=${HF_TOKEN} \
    --dry-run=client -o yaml | kubectl -n "$NAMESPACE" apply -f -
# OR
kubectl apply -n $NAMESPACE -f hf-token-secret.yaml
```

## Create PVC
```bash
kubectl apply -n $NAMESPACE -f <pvc-file-name>.yaml
```

### Check PVC status
Check that the PVC is **Bound**:
```bash
kubectl -n $NAMESPACE get pvc
```
If not bound, troubleshoot with:
```bash
kubectl -n $NAMESPACE describe pvc <pvc-name>
```

## Deploy
kubectl apply -n $NAMESPACE -f vllm-deployment-name.yaml

### Check deployment status
```bash
# Check ready: Wait until "get pods" shows READY=1/1 and STATUS=Running.
kubectl -n $NAMESPACE get pods -o wide
kubectl -n $NAMESPACE get pods -w
kubectl -n $NAMESPACE describe pod -l app=qwen3-server | sed -n '/Events/,$p'

# View the logs from the running Deployment
# E.g: ./kubernetes/vllm-qwen3-32b.yaml
kubectl -n $NAMESPACE logs -f -l app=qwen3-server

# Check for model download progress:
kubectl -n $NAMESPACE exec -it deploy/vllm-qwen3-deployment -- bash -lc 'du -sh /root/.cache/huggingface 2>/dev/null || true; ls -lh /root/.cache/huggingface/hub 2>/dev/null || true'


```

## Now GPU should be shown:
```bash
kubectl get nodes -L cloud.google.com/gke-accelerator \
  -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu

# OR Check if GPU nodes are available
kubectl get nodes -o wide
# Verify GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

## Access the vLLM Service
### With LoadBalancer Service (Automatic)
The LoadBalancer service automatically creates an external IP. Check the service status:
```bash
kubectl -n $NAMESPACE get svc vllm-server

# Test with a question
# http://<EXTERNAL-IP>:8000/ OR http://<EXTERNAL-IP>/ ???
curl http://<EXTERNAL-IP>:8000/v1/chat/completions \
-X POST \
-H "Content-Type: application/json" \
-d '{
    "model": "google/gemma-3-1b-it",
    "messages": [
        {
          "role": "user",
          "content": "Why is the sky blue?"
        }
    ],
    "temperature": 0
}'

```
Look for the `EXTERNAL-IP` column to get your external IP address.

### Port-Forward for Local/Internal Access
```bash
# port-forward: Your Service is ClusterIP, so it’s only reachable inside the cluster. kubectl port-forward service/llm-service 8000:8000 creates a temporary local tunnel so you can test the API at http://127.0.0.1:8000 from your Cloud Shell or laptop.
kubectl -n $NAMESPACE port-forward service/{service-name} 8000:8000

# Test with a question
curl http://127.0.0.1:8000/v1/chat/completions \
-X POST \
-H "Content-Type: application/json" \
-d '{
    "model": "google/gemma-3-1b-it",
    "messages": [
        {
          "role": "user",
          "content": "Why is the sky blue?"
        }
    ]
}'
```

## Clean Up

### 1. **Remove vLLM Resources**
```bash
# Remove deployment (choose the one you deployed)
kubectl delete -f kubernetes/vllm-deployment-mistral-7b-gke.yaml
# OR
kubectl delete -f kubernetes/vllm-deployment-gke.yaml

# Remove other resources
kubectl delete -f kubernetes/vllm-service-gke.yaml
# OR if using internal service
# kubectl delete -f kubernetes/vllm-service-internal-gke.yaml
kubectl delete -f kubernetes/vllm-pvc-gke.yaml
```

### 2. **Delete GKE Cluster**
```bash
gcloud container clusters delete vllm-cluster --zone=us-central1-a
```

### 3. **Clean Up LoadBalancer (Automatic)**
The LoadBalancer service is automatically cleaned up when you delete the service. No manual cleanup needed.



## Troubleshooting

### 1. **GPU Not Available**
```bash
# Check GPU operator status
kubectl get pods -n kube-system | grep nvidia

# Check GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

### 2. **PVC Not Binding**
```bash
# Check available storage classes
kubectl get storageclass

# Check PV status
kubectl get pv
```

### 3. **Pod Stuck in Pending**
```bash
# Check pod events
kubectl describe pod <pod-name>

# Check node resources
kubectl describe nodes
```

### 4. **Service Not Accessible**
```bash
# Check service status
kubectl get svc

# Check endpoints
kubectl get endpoints vllm-server
```

## References

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE GPU Support](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Kubernetes GPU Support](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [GKE Storage Classes](https://cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes)


## vLLM Args
```bash
# --enable-reasoning is removed since vLLM v0.10.0
usage: api_server.py [-h] [--headless] [--api-server-count API_SERVER_COUNT]
                     [--config CONFIG] [--host HOST] [--port PORT]
                     [--uvicorn-log-level {critical,debug,error,info,trace,warning}]
                     [--disable-uvicorn-access-log | --no-disable-uvicorn-access-log]
                     [--allow-credentials | --no-allow-credentials]
                     [--allowed-origins ALLOWED_ORIGINS]
                     [--allowed-methods ALLOWED_METHODS]
                     [--allowed-headers ALLOWED_HEADERS] [--api-key API_KEY]
                     [--lora-modules LORA_MODULES [LORA_MODULES ...]]
                     [--chat-template CHAT_TEMPLATE]
                     [--chat-template-content-format {auto,openai,string}]
                     [--response-role RESPONSE_ROLE]
                     [--ssl-keyfile SSL_KEYFILE] [--ssl-certfile SSL_CERTFILE]
                     [--ssl-ca-certs SSL_CA_CERTS]
                     [--enable-ssl-refresh | --no-enable-ssl-refresh]
                     [--ssl-cert-reqs SSL_CERT_REQS] [--root-path ROOT_PATH]
                     [--middleware MIDDLEWARE]
                     [--return-tokens-as-token-ids | --no-return-tokens-as-token-ids]
                     [--disable-frontend-multiprocessing | --no-disable-frontend-multiprocessing]
                     [--enable-request-id-headers | --no-enable-request-id-headers]
                     [--enable-auto-tool-choice | --no-enable-auto-tool-choice]
                     [--tool-call-parser {deepseek_v3,glm4_moe,granite-20b-fc,granite,hermes,hunyuan_a13b,internlm,jamba,kimi_k2,llama4_pythonic,llama4_json,llama3_json,minimax,mistral,phi4_mini_json,pythonic,qwen3_coder,xlam}]
                     [--tool-parser-plugin TOOL_PARSER_PLUGIN]
                     [--log-config-file LOG_CONFIG_FILE]
                     [--max-log-len MAX_LOG_LEN]
                     [--disable-fastapi-docs | --no-disable-fastapi-docs]
                     [--enable-prompt-tokens-details | --no-enable-prompt-tokens-details]
                     [--enable-server-load-tracking | --no-enable-server-load-tracking]
                     [--enable-force-include-usage | --no-enable-force-include-usage]
                     [--enable-tokenizer-info-endpoint | --no-enable-tokenizer-info-endpoint]
                     [--model MODEL]
                     [--task {auto,classify,draft,embed,embedding,generate,reward,score,transcription}]
                     [--tokenizer TOKENIZER]
                     [--tokenizer-mode {auto,custom,mistral,slow}]
                     [--trust-remote-code | --no-trust-remote-code]
                     [--dtype {auto,bfloat16,float,float16,float32,half}]
                     [--seed SEED] [--hf-config-path HF_CONFIG_PATH]
                     [--allowed-local-media-path ALLOWED_LOCAL_MEDIA_PATH]
                     [--revision REVISION] [--code-revision CODE_REVISION]
                     [--rope-scaling ROPE_SCALING] [--rope-theta ROPE_THETA]
                     [--tokenizer-revision TOKENIZER_REVISION]
                     [--max-model-len MAX_MODEL_LEN]
                     [--quantization QUANTIZATION]
                     [--enforce-eager | --no-enforce-eager]
                     [--max-seq-len-to-capture MAX_SEQ_LEN_TO_CAPTURE]
                     [--max-logprobs MAX_LOGPROBS]
                     [--logprobs-mode {processed_logits,processed_logprobs,raw_logits,raw_logprobs}]
                     [--disable-sliding-window | --no-disable-sliding-window]
                     [--disable-cascade-attn | --no-disable-cascade-attn]
                     [--skip-tokenizer-init | --no-skip-tokenizer-init]
                     [--enable-prompt-embeds | --no-enable-prompt-embeds]
                     [--served-model-name SERVED_MODEL_NAME [SERVED_MODEL_NAME ...]]
                     [--disable-async-output-proc]
                     [--config-format {auto,hf,mistral}]
                     [--hf-token [HF_TOKEN]] [--hf-overrides HF_OVERRIDES]
                     [--override-neuron-config OVERRIDE_NEURON_CONFIG]
                     [--override-pooler-config OVERRIDE_POOLER_CONFIG]
                     [--logits-processor-pattern LOGITS_PROCESSOR_PATTERN]
                     [--generation-config GENERATION_CONFIG]
                     [--override-generation-config OVERRIDE_GENERATION_CONFIG]
                     [--enable-sleep-mode | --no-enable-sleep-mode]
                     [--model-impl {auto,vllm,transformers}]
                     [--override-attention-dtype OVERRIDE_ATTENTION_DTYPE]
                     [--load-format {auto,pt,safetensors,npcache,dummy,tensorizer,sharded_state,gguf,bitsandbytes,mistral,runai_streamer,runai_streamer_sharded,fastsafetensors}]
                     [--download-dir DOWNLOAD_DIR]
                     [--model-loader-extra-config MODEL_LOADER_EXTRA_CONFIG]
                     [--ignore-patterns IGNORE_PATTERNS [IGNORE_PATTERNS ...]]
                     [--use-tqdm-on-load | --no-use-tqdm-on-load]
                     [--pt-load-map-location PT_LOAD_MAP_LOCATION]
                     [--guided-decoding-backend {auto,guidance,lm-format-enforcer,outlines,xgrammar}]
                     [--guided-decoding-disable-fallback | --no-guided-decoding-disable-fallback]
                     [--guided-decoding-disable-any-whitespace | --no-guided-decoding-disable-any-whitespace]
                     [--guided-decoding-disable-additional-properties | --no-guided-decoding-disable-additional-properties]
                     [--reasoning-parser {deepseek_r1,glm4_moe,granite,hunyuan_a13b,mistral,qwen3}]
                     [--distributed-executor-backend {external_launcher,mp,ray,uni,None}]
                     [--pipeline-parallel-size PIPELINE_PARALLEL_SIZE]
                     [--tensor-parallel-size TENSOR_PARALLEL_SIZE]
                     [--data-parallel-size DATA_PARALLEL_SIZE]
                     [--data-parallel-rank DATA_PARALLEL_RANK]
                     [--data-parallel-start-rank DATA_PARALLEL_START_RANK]
                     [--data-parallel-size-local DATA_PARALLEL_SIZE_LOCAL]
                     [--data-parallel-address DATA_PARALLEL_ADDRESS]
                     [--data-parallel-rpc-port DATA_PARALLEL_RPC_PORT]
                     [--data-parallel-backend DATA_PARALLEL_BACKEND]
                     [--data-parallel-hybrid-lb | --no-data-parallel-hybrid-lb]
                     [--enable-expert-parallel | --no-enable-expert-parallel]
                     [--enable-eplb | --no-enable-eplb]
                     [--num-redundant-experts NUM_REDUNDANT_EXPERTS]
                     [--eplb-window-size EPLB_WINDOW_SIZE]
                     [--eplb-step-interval EPLB_STEP_INTERVAL]
                     [--eplb-log-balancedness | --no-eplb-log-balancedness]
                     [--max-parallel-loading-workers MAX_PARALLEL_LOADING_WORKERS]
                     [--ray-workers-use-nsight | --no-ray-workers-use-nsight]
                     [--disable-custom-all-reduce | --no-disable-custom-all-reduce]
                     [--worker-cls WORKER_CLS]
                     [--worker-extension-cls WORKER_EXTENSION_CLS]
                     [--enable-multimodal-encoder-data-parallel | --no-enable-multimodal-encoder-data-parallel]
                     [--block-size {1,8,16,32,64,128}]
                     [--gpu-memory-utilization GPU_MEMORY_UTILIZATION]
                     [--swap-space SWAP_SPACE]
                     [--kv-cache-dtype {auto,fp8,fp8_e4m3,fp8_e5m2,fp8_inc}]
                     [--num-gpu-blocks-override NUM_GPU_BLOCKS_OVERRIDE]
                     [--enable-prefix-caching | --no-enable-prefix-caching]
                     [--prefix-caching-hash-algo {builtin,sha256,sha256_cbor_64bit}]
                     [--cpu-offload-gb CPU_OFFLOAD_GB]
                     [--calculate-kv-scales | --no-calculate-kv-scales]
                     [--limit-mm-per-prompt LIMIT_MM_PER_PROMPT]
                     [--media-io-kwargs MEDIA_IO_KWARGS]
                     [--mm-processor-kwargs MM_PROCESSOR_KWARGS]
                     [--disable-mm-preprocessor-cache | --no-disable-mm-preprocessor-cache]
                     [--interleave-mm-strings | --no-interleave-mm-strings]
                     [--enable-lora | --no-enable-lora]
                     [--enable-lora-bias | --no-enable-lora-bias]
                     [--max-loras MAX_LORAS] [--max-lora-rank MAX_LORA_RANK]
                     [--lora-extra-vocab-size LORA_EXTRA_VOCAB_SIZE]
                     [--lora-dtype {auto,bfloat16,float16}]
                     [--max-cpu-loras MAX_CPU_LORAS]
                     [--fully-sharded-loras | --no-fully-sharded-loras]
                     [--default-mm-loras DEFAULT_MM_LORAS]
                     [--speculative-config SPECULATIVE_CONFIG]
                     [--show-hidden-metrics-for-version SHOW_HIDDEN_METRICS_FOR_VERSION]
                     [--otlp-traces-endpoint OTLP_TRACES_ENDPOINT]
                     [--collect-detailed-traces {all,model,worker,None} [{all,model,worker,None} ...]]
                     [--max-num-batched-tokens MAX_NUM_BATCHED_TOKENS]
                     [--max-num-seqs MAX_NUM_SEQS]
                     [--max-num-partial-prefills MAX_NUM_PARTIAL_PREFILLS]
                     [--max-long-partial-prefills MAX_LONG_PARTIAL_PREFILLS]
                     [--cuda-graph-sizes CUDA_GRAPH_SIZES [CUDA_GRAPH_SIZES ...]]
                     [--long-prefill-token-threshold LONG_PREFILL_TOKEN_THRESHOLD]
                     [--num-lookahead-slots NUM_LOOKAHEAD_SLOTS]
                     [--scheduler-delay-factor SCHEDULER_DELAY_FACTOR]
                     [--preemption-mode {recompute,swap,None}]
                     [--num-scheduler-steps NUM_SCHEDULER_STEPS]
                     [--multi-step-stream-outputs | --no-multi-step-stream-outputs]
                     [--scheduling-policy {fcfs,priority}]
                     [--enable-chunked-prefill | --no-enable-chunked-prefill]
                     [--disable-chunked-mm-input | --no-disable-chunked-mm-input]
                     [--scheduler-cls SCHEDULER_CLS]
                     [--disable-hybrid-kv-cache-manager | --no-disable-hybrid-kv-cache-manager]
                     [--async-scheduling | --no-async-scheduling]
                     [--kv-transfer-config KV_TRANSFER_CONFIG]
                     [--kv-events-config KV_EVENTS_CONFIG]
                     [--compilation-config COMPILATION_CONFIG]
                     [--additional-config ADDITIONAL_CONFIG]
                     [--disable-log-stats] [--enable-prompt-adapter]
                     [--disable-log-requests]
                     [model_tag]
```