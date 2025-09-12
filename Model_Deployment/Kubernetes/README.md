# vLLM Deployment Guide using K8S

## Table of Contents


## Next steps:
- [X] Deploy Qwen3-32b (using 2 A100-40GB GPUs). Since it's too large, we must set `--max-model-len=8000`
- [ ] Expose deployment ([Exposing applications using services](https://cloud.google.com/kubernetes-engine/docs/how-to/exposing-apps))
- [ ] Add monitoring
- [ ] Optimizing (use TPU):
    - https://www.aleksagordic.com/blog/vllm
    - https://docs.vllm.ai/en/latest/getting_started/installation/aws_neuron.html
    - https://docs.vllm.ai/en/stable/getting_started/installation/aws_neuron.html
    - https://huggingface.co/docs/optimum-neuron/training_tutorials/qwen3-fine-tuning
    - https://aws.amazon.com/blogs/machine-learning/how-to-run-qwen-2-5-on-aws-ai-chips-using-hugging-face-libraries/
    - neu dung GCP thi co TPU: https://docs.vllm.ai/en/stable/getting_started/installation/google_tpu.html

## Getting Ready

### Verify info
#### On Ori
Website (https://www.ori.co/)
1. Create a new Kubernetes cluster
    1. Choose location
    1. Select GPU:
        - gpu.nvidia.com/class:H100SXM-80
        - gpu.nvidia.com/class:H200SXM-141
        - gpu.nvidia.com/class:L4
        - gpu.nvidia.com/class:L40S
    1. Download *KubeConfig* file (E.g. `Ori-k8s/kubeConfig.yaml`)

#### On GKE
1. Enable "[Google Kubernetes Engine API](https://cloud.google.com/kubernetes-engine/docs/how-to/consuming-reservations#before_you_begin)"
1. GPU available on GKE:
    - [About GPUs in Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/docs/concepts/gpus)
    - [IAM quotas page](https://console.cloud.google.com/iam-admin/quotas) to ensure that you have enough GPUs available in your project. Your GPU quota should be at least equal to the total number of GPUs you intend to run in your cluster.
    - If you enable cluster autoscaling ([About GKE cluster autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)), you should request GPU quota at least equivalent to your cluster's maximum number of nodes multiplied by the number of GPUs per node.
    - To request additional GPU quota, follow the instructions to [request a quota adjustment](https://cloud.google.com/docs/quotas/view-manage#requesting_higher_quota), using gpus as the metric.
1. [GPU regions and zones](https://cloud.google.com/compute/docs/gpus/gpu-regions-zones) for suitable region and zone with compatible GPU. Those are available [regions & zones](https://cloud.google.com/compute/docs/regions-zones)
1. [About GKE modes of operation](https://cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode) to choose b/w Autopilot (recommended) and Standard mode




##### GPU types
https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus
Replace GPU_TYPE with the type of GPU in your target nodes. This can be one of the following:
- `nvidia-b200`: NVIDIA B200 (180GB)
- `nvidia-h200-141gb`: NVIDIA H200 (141GB)
- `nvidia-h100-mega-80gb`: NVIDIA H100 Mega (80GB)
- `nvidia-h100-80gb`: NVIDIA H100 (80GB)
- `nvidia-a100-80gb`: NVIDIA A100 (80GB)
- `nvidia-tesla-a100`: NVIDIA A100 (40GB)
- `nvidia-l4`: NVIDIA L4
- `nvidia-tesla-t4`: NVIDIA T4

#### Model Size Resource Requirements

| Model Size Range (Parameters) | System RAM (requests) | System RAM (limits) | PVC Storage | Recommended GPU | Examples |
|------------------|----------------------|---------------------|-------------|-----------------|----------|
| **≤5B** | 4-6GB | 8-12GB | 20-30GB | nvidia-l4, nvidia-tesla-t4 | Gemma-2B (2.27B), Phi-3-mini (3.8B), Qwen2-1.5B (1.5B) |
| **5-10B** | 6-10GB | 12-20GB | 30-50GB | nvidia-l4, nvidia-tesla-a100 | Gemma-7B (7B), Llama-3.1-8B (8B), Mistral-7B (7B) |
| **10-30B** | 10-16GB | 20-32GB | 50-80GB | nvidia-tesla-a100, nvidia-a100-80gb | Llama-3.1-70B (70B, quantized), Qwen2.5-32B (32B) |
| **30-50B** | 16-24GB | 32-48GB | 80-120GB | nvidia-a100-80gb, nvidia-h100-80gb | Mixtral-8x7B (56B), Llama-3.1-70B (70B) |
| **50-70B** | 24-32GB | 48-64GB | 120-200GB | nvidia-h100-80gb, nvidia-h100-mega-80gb | Qwen2.5-72B (72B), Llama-3.1-405B (405B, quantized) |
| **70-150B** | 32-48GB | 64-96GB | 200-300GB | nvidia-h100-mega-80gb, nvidia-h200-141gb | Large quantized models, Mixtral-8x22B (176B) |
| **150B+** | 48-64GB | 96-128GB | 300-500GB | nvidia-h200-141gb, nvidia-b200 | Llama-3.1-405B (405B), GPT-4 class models |

##### Resource Guidelines:
- **System RAM**: Used for model loading, CPU computations, and vLLM framework overhead
- **PVC Storage**: Used for persistent model cache, avoiding re-downloads on pod restarts
- **GPU Memory**: Should be 1.5-2x the model size for optimal performance
- **Shared Memory (dshm)**: 2-8GB depending on model size and tensor parallel configuration

##### Notes:
- For models >70B parameters, consider using tensor parallelism across multiple GPUs
- Quantized models (4-bit, 8-bit) require significantly less GPU memory
- Add 20-30% buffer to PVC storage for model updates and temporary files
- Monitor actual usage and adjust resources based on workload patterns
- Parameter counts are approximate and may vary between model variants

## Prepare environment
### On Ori
Set Up Kubeconfig: This `kubeConfig.yaml` file can be downloaded from Ori after creating a K8S cluster
```bash
export KUBECONFIG=<path>/kubeConfig.yaml
```

### On GKE
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


## Create & connect a GKE cluster (GKE only)

### Create cluster:
Select select 1 mode to create cluster

- Autopilot (recommend)
    ```bash
    gcloud container clusters create-auto $CLUSTER_NAME \
        --project=$PROJECT_ID \
        --location=$CONTROL_PLANE_LOCATION \
        --release-channel=rapid
    ```

- Standard:
    ```bash
    gcloud container clusters create $CLUSTER_NAME \
        --project=$PROJECT_ID \
        --region=$REGION \
        --machine-type g2-standard-8 \
        --accelerator type=nvidia-l4,count=1 \
        --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
    ```
Reference:
- https://cloud.google.com/sdk/gcloud/reference/container/clusters/create

### Connect to cluster
```bash
gcloud container clusters get-credentials $CLUSTER_NAME \
    --location=$REGION
```

### Create namespace
```bash
kubectl create namespace "$NAMESPACE" || true

# Optionally set the default namespace for this context
kubectl config set-context --current --namespace="$NAMESPACE"
```

### Verify cluster and namespace info
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

## Both Ori and GKE
From here, not that Ori does not need `$NAMESPACE`.
E.g.:
```bash
# Ori
kubectl apply -f some-file.yaml
# GKE
kubectl -n $NAMESPACE apply -f some-file.yaml
```

## Create a Kubernetes secret for Hugging Face credentials
Remember to add credentials into `hf-token-secret.yaml` file.
```bash
kubectl -n $NAMESPACE apply -f hf-token-secret.yaml
```
OR
```bash
kubectl -n $NAMESPACE create secret generic hf-secret \
    --from-literal=hf_api_token=${HF_TOKEN} \
    --dry-run=client -o yaml | kubectl -n "$NAMESPACE" apply -f -
```

Verify the secret was created:
```bash
kubectl -n $NAMESPACE get secrets
```

## Persistent Volume Claim (PVC)
This PVC is used to cache Hugging Face models for vLLM.

### Create PVC
Remember to adjust storage requested in `<pvc-file>.yaml` (E.g. `vllm-pvc.yaml`) according to model size.
Apply the PVC:
```bash
kubectl -n $NAMESPACE apply -f <pvc-file>.yaml
```

### Check PVC status
Check that the PVC is **Bound**, especially after deploying model:
```bash
kubectl -n $NAMESPACE get pvc
```
If not bound, troubleshoot (E.g. `<pvc-name>` is `vllm-models` from `Ori-k8s/vllm-pvc.yaml`):
```bash
kubectl -n $NAMESPACE describe pvc <pvc-name>
```

## Deploy LLM
The deployment cmd will launch the vLLM server with GPU support and mount the model cache PVC.

```bash
kubectl -n $NAMESPACE apply -f vllm-deployment-name.yaml
```

### Check status

```bash
# Check ready: Wait until "get pods" shows READY=1/1 and STATUS=Running.
kubectl -n $NAMESPACE get pods -o wide
kubectl -n $NAMESPACE get pods -w
kubectl -n $NAMESPACE describe pod -l app=qwen3-server | sed -n '/Events/,$p'

# View the logs from the running Deployment. E.g: ./kubernetes/vllm-qwen3-32b.yaml
kubectl -n $NAMESPACE logs -f -l app=qwen3-server
# OR vllm-server is metadata.name
kubectl -n $NAMESPACE logs deployment/vllm-server

# Check for model download progress:
kubectl -n $NAMESPACE exec -it deploy/vllm-qwen3-deployment -- bash -lc 'du -sh /root/.cache/huggingface 2>/dev/null || true; ls -lh /root/.cache/huggingface/hub 2>/dev/null || true'
```
**Note**:
1. If the pod is stuck in `Pending` or `ContainerCreating`, see Troubleshooting below.

### Check GPU using:
```bash
kubectl get nodes -L cloud.google.com/gke-accelerator \
  -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu

# OR Check if GPU nodes are available
kubectl get nodes -o wide
# Verify GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

## Expose the vLLM Service
Create service -> expose model to specific port depending on method.

1. **vLLM API**: `http://<vllm-server-<external/internal>-ip>:8000`
2. **vLLM Metrics**: `http://<vllm-server-<external/internal>-ip>:8000/metrics`

### LoadBalancer Service (recommend)
The LoadBalancer service automatically creates an external IP. Check the service status:

1. Apply the service:
```bash
kubectl -n $NAMESPACE apply -f vllm-service.yaml
```
1. Look for the `EXTERNAL-IP` column to get your external IP address (E.g. `<service-name>` is `vllm-server` from `Ori-k8s/vllm-service.yaml`).
    ```bash
    kubectl -n $NAMESPACE get svc <service-name>
    ```
    - If `EXTERNAL-IP` is assigned, you can access the API from outside the cluster.
    - If not, or for local testing, use port-forwarding below.

1. Test with a question. In a new terminal, run:
    ```bash
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

### Port-Forward for Local/Internal Access
Your Service is ClusterIP, so it’s only reachable inside the cluster. kubectl port-forward service/llm-service 8000:8000 creates a temporary local tunnel so you can test the API at http://127.0.0.1:8000 from your Cloud Shell or laptop.

1. Forward port
```bash
kubectl -n $NAMESPACE port-forward service/{service-name} 8000:8000
```
You should see:
```bash
Forwarding from 127.0.0.1:8000 -> 8000
```

1. Test with a question. In a new terminal, run:
    ```bash
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

## Monitoring (Kubernetes Native - Recommended for Production)

### Deploy
In `Monitoring/`
```bash
kubectl -n $NAMESPACE apply -f prometheus-deployment.yaml

kubectl -n $NAMESPACE apply -f grafana-deployment.yaml
```

Wait for monitoring services to be ready
```bash
kubectl -n $NAMESPACE wait --for=condition=available --timeout=300s deployment/prometheus
kubectl -n $NAMESPACE wait --for=condition=available --timeout=300s deployment/grafana
```

### Verification
```bash
kubectl -n $NAMESPACE get svc vllm-server
kubectl -n $NAMESPACE get svc prometheus
kubectl -n $NAMESPACE get svc grafana
```

## Monitoring (Docker Compose Setup)
1. Get vLLM External IP
```bash
# Get the external IP
kubectl -n $NAMESPACE get svc vllm-server -o wide

# If using port-forward (for local development)
kubectl -n $NAMESPACE port-forward svc/vllm-server 8000:8000
```

1. Update Prometheus Configuration
Edit `prometheus_grafana/prometheus.yaml` and replace `host.docker.internal:8000` with your vLLM service IP:

```yaml
scrape_configs:
  - job_name: vllm
    static_configs:
      - targets:
          - 'YOUR_VLLM_IP:8000'  # Replace with your vLLM IP
```

1. Start Monitoring with Docker Compose
```bash
cd prometheus_grafana
docker-compose up -d
```

### Verification
```bash
# For Docker Compose approach
docker-compose -f prometheus_grafana/docker-compose.yaml ps
```

## Accessing Monitoring Services

### Access
1. To get external IPs, run:
    ```bash
    kubectl -n $NAMESPACE get svc
    ```

1. URLs:
    - Prometheus: `http://<prometheus-external-ip>:9090` (K8s) OR `http://localhost:9090` (Docker)
    - Grafana: `http://<grafana-external-ip>:3000` (K8s) OR `http://localhost:3000`(Docker)

## Setting Up Grafana Dashboard
1. Open your browser and go to the Grafana URL (`http://<grafana-external-ip>:3000`)
1. Login with:
   - Username: `admin`
   - Password: `admin`
1. Go to **Dashboards** → **Import**
1. Click **Upload JSON file**. Select the `prometheus_grafana/grafana.json` file
1. Click **Load**
1. Select **Prometheus** as the data source
1. Click **Import**

## Configure Monitor Dashboard
The dashboard includes variables for model selection. You can:
- Select different models from the dropdown
- Adjust time ranges
- View various metrics including:
  - E2E Request Latency
  - Token Throughput
  - Time Per Output Token Latency
  - Scheduler State
  - Time To First Token Latency
  - Cache Utilization
  - Request Prompt/Generation Length Heatmaps

The dashboard shows real-time metrics from your vLLM deployment, including:
- **Request Latency**: End-to-end request processing time
- **Token Throughput**: Tokens processed per second
- **Scheduler State**: Number of running and waiting requests
- **Cache Utilization**: GPU cache usage percentage
- **Request Patterns**: Heatmaps showing prompt and generation lengths

### Useful Commands for Monitoring

```bash
# Check pod logs (Kubernetes approach)
kubectl logs -l app.kubernetes.io/name=vllm
kubectl logs -l app=prometheus
kubectl logs -l app=grafana

# Check Docker logs (Docker Compose approach)
docker-compose -f prometheus_grafana/docker-compose.yaml logs

# Port forward for local access (Kubernetes)
kubectl port-forward svc/vllm-server 8000:8000
kubectl port-forward svc/prometheus 9090:9090
kubectl port-forward svc/grafana 3000:3000

# Check service endpoints
kubectl get endpoints
```

## Testing the LLM
### Generate Load for Monitoring

You can test the monitoring by sending requests to your vLLM API:

#### Option 1: Using the Test Script

Use the provided test script to generate significant load:

```bash
# Run the test script (sends 1000 requests)
python src/test_vllm_api.py
```

This script will:
- Send 1000 completion requests to your vLLM API
- Generate metrics that will appear in Grafana
- Show real-time performance data

#### Option 2: Manual Testing

```bash
# Test a simple completion request
curl -X POST "http://<vllm-server-external-ip>:8000/v1/completions" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "facebook/opt-125m",
    "prompt": "Hello, how are you?",
    "max_tokens": 50
  }'
```



## Clean Up

### Remove vLLM Resources
1. To remove all vLLM resources:
```bash
# Remove monitoring
kubectl -n $NAMESPACE delete -f grafana-deployment.yaml
kubectl -n $NAMESPACE delete -f prometheus-deployment.yaml

# Remove service
kubectl -n $NAMESPACE delete -f vllm-service.yaml

# Remove deployment
kubectl -n $NAMESPACE delete -f vllm-deployment.yaml

# Remove PVC
kubectl -n $NAMESPACE delete -f vllm-pvc.yaml

# Remove secrets
kubectl -n $NAMESPACE delete -f hf-token-secret.yaml
```

### Remove Docker Compose Cleanup

```bash
cd prometheus_grafana
docker-compose down
```

2. Delete Any Remaining Pods or Services
If you want to ensure everything is gone, you can list and delete all pods and services in the default namespace:
```bash
kubectl get pods
kubectl get svc
kubectl get secrets
```
Then, for any remaining resources:
```bash
kubectl delete pod <pod-name>
kubectl delete svc <service-name>
kubectl delete secret <secret-name>
```

3. (Optional) Delete PVCs and Secrets
If you created any other PVCs or secrets:
```bash
kubectl get pvc
kubectl delete pvc <pvc-name>

kubectl get secrets
kubectl delete secret <secret-name>
```

### Clean Up LoadBalancer
The LoadBalancer service is automatically cleaned up when you delete the service. No manual cleanup needed.

### Delete GKE Cluster
```bash
gcloud container clusters delete vllm-cluster --zone=us-central1-a
```



## Troubleshooting

### GPU Not Available
```bash
# Check GPU operator status
kubectl get pods -n kube-system | grep nvidia

# Check GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

### PVC Not Binding
```bash
# Check available storage classes
kubectl get storageclass

# Check PV status
kubectl get pv
```

### Pod Stuck in Pending
- **PVC not bound:** Ensure you applied the PVC and it is `Bound` (`kubectl get pvc`).
- **No available GPU:** Make sure no other pods are using the GPU, and your node has available GPU resources.
- **Node selector mismatch:** The deployment uses `nodeSelector: gpu.nvidia.com/class: L40S`. Ensure your node has this label.

```bash
# Check pod events
kubectl describe pod <pod-name>

# Check node resources
kubectl describe nodes
```

### Pod Stuck in ContainerCreating
- **Image pulling:** The node may be downloading the Docker image. This can take several minutes on a fresh node.
- **PVC mounting:** Wait for the PVC to attach. If it fails, check `kubectl describe pod <pod-name>` for errors.

### Service Not Accessible
- **No EXTERNAL-IP:** Use port-forwarding for local access.
- **Port-forward fails:** Ensure the pod is `Running` and listening on port 8000.

```bash
# Check service status
kubectl get svc

# Check endpoints
kubectl get endpoints vllm-server
```

### Private Model Authentication Issues
- **Invalid token:** Ensure your Hugging Face token is correct and has access to the private model.
- **Model not found:** Verify the model name in the deployment args matches your private model exactly.
- **Permission denied:** Check that your token has the necessary permissions to access the private model.

### Check Events and Logs
- For detailed error messages, use:
  ```bash
  kubectl describe pod <pod-name>
  kubectl logs <pod-name>
  ```

## Architecture Overview

### Option 1: Kubernetes-Native
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   vLLM Server   │    │   Prometheus    │    │     Grafana     │
│   (OPT-125m)    │    │   (Metrics)     │    │   (Dashboard)   │
│                 │    │                 │    │                 │
│ Port: 8000      │◄───┤ Port: 9090      │◄───┤ Port: 3000      │
│ /metrics        │    │ Scrapes vLLM    │    │ Visualizes      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### Option 2: Docker Compose (Following README.md)
```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   vLLM Server   │    │   Prometheus    │    │     Grafana     │
│   (Kubernetes)  │    │   (Docker)      │    │   (Docker)      │
│                 │    │                 │    │                 │
│ Port: 8000      │◄───┤ Port: 9090      │◄───┤ Port: 3000      │
│ /metrics        │    │ Scrapes vLLM    │    │ Visualizes      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

Both approaches work as follows:
1. vLLM exposes metrics at `/metrics` endpoint
2. Prometheus scrapes these metrics every 5 seconds
3. Grafana queries Prometheus to display dashboards 

## References

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE GPU Support](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Kubernetes GPU Support](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [GKE Storage Classes](https://cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes)

- Tutorial: [Serve Llama models using GPUs on GKE with vLLM](https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-llama-gpus-vllm)

- Tutorial: [Serve Gemma open models using GPUs on GKE with vLLM](https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm)

- Request GPU in GKE: https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus

- [vLLM Kubernetes Deployment Guide](https://docs.vllm.ai/en/stable/deployment/k8s.html#deployment-with-gpus)
- [Ori Stable Diffusion Kubernetes Example](https://docs.ori.co/kubernetes/examples/stable-diffusion/)
- [Hugging Face Private Models](https://huggingface.co/docs/hub/security-tokens)

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