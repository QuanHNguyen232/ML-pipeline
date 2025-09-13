# vLLM Deployment Guide using K8S

## Table of Contents

1. [Next Steps](#next-steps)
1. [Getting Ready (Ori + GKE)](#getting-ready-ori--gke)
1. [Prepare Environment (Ori + GKE)](#prepare-environment-ori--gke)
1. [Create & Connect a GKE Cluster (GKE only)](#create--connect-a-gke-cluster-gke-only)
1. [Create Secret for HF Credentials (Ori + GKE)](#create-secret-for-hf-credentials-ori--gke)
1. [Persistent Volume Claim (PVC) (Ori + GKE)](#persistent-volume-claim-pvc-ori--gke)
1. [Deploy LLM (Ori + GKE)](#deploy-llm-ori--gke)
1. [Expose the vLLM Service (Ori + GKE)](#expose-the-vllm-service-ori--gke)
1. [Monitoring Services (Ori + GKE)](#monitoring-services-ori--gke)
1. [Testing the LLM (Ori + GKE)](#testing-the-llm-ori--gke)
1. [Clean Up (Ori + GKE)](#clean-up-ori--gke)
1. [Troubleshooting (Ori + GKE)](#troubleshooting-ori--gke)
1. [Architecture Overview](#architecture-overview)
1. [References](#references)

## Next steps:
- [X] Deploy Qwen3-32b (using 2 A100-40GB GPUs). Since it's too large, we must set `--max-model-len=8000`
- [X] Expose deployment ([Exposing applications using services](https://cloud.google.com/kubernetes-engine/docs/how-to/exposing-apps))
- [X] Add monitoring (Grafana/Prometheus)
- [ ] Optimizing (use TPU):
    - https://www.aleksagordic.com/blog/vllm
    - https://docs.vllm.ai/en/latest/getting_started/installation/aws_neuron.html
    - https://docs.vllm.ai/en/stable/getting_started/installation/aws_neuron.html
    - https://huggingface.co/docs/optimum-neuron/training_tutorials/qwen3-fine-tuning
    - https://aws.amazon.com/blogs/machine-learning/how-to-run-qwen-2-5-on-aws-ai-chips-using-hugging-face-libraries/
    - neu dung GCP thi co TPU: https://docs.vllm.ai/en/stable/getting_started/installation/google_tpu.html

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>


## Getting Ready (Ori + GKE)

### On Ori
1. Website (https://www.ori.co/) or login (https://console.ogc.ori.co/)
1. Create a new Kubernetes cluster
    1. Choose location
    1. Select GPU:
        - gpu.nvidia.com/class:H100SXM-80
        - gpu.nvidia.com/class:H200SXM-141
        - gpu.nvidia.com/class:L4
        - gpu.nvidia.com/class:L40S
    1. Download ***KubeConfig*** file (E.g. `./Ori/kubeConfig.yaml`)

### On GKE
1. Enable "[Google Kubernetes Engine API](https://cloud.google.com/kubernetes-engine/docs/how-to/consuming-reservations#before_you_begin)"
1. GPU available on GKE:
    - [About GPUs in Google Kubernetes Engine (GKE)](https://cloud.google.com/kubernetes-engine/docs/concepts/gpus)
    - [IAM quotas page](https://console.cloud.google.com/iam-admin/quotas) to ensure that you have enough GPUs available in your project. Your GPU quota should be at least equal to the total number of GPUs you intend to run in your cluster.
    - If you enable cluster autoscaling ([About GKE cluster autoscaling](https://cloud.google.com/kubernetes-engine/docs/concepts/cluster-autoscaler)), you should request GPU quota at least equivalent to your cluster's maximum number of nodes multiplied by the number of GPUs per node.
    - To request additional GPU quota, follow the instructions to [request a quota adjustment](https://cloud.google.com/docs/quotas/view-manage#requesting_higher_quota), using gpus as the metric.
1. [GPU regions and zones](https://cloud.google.com/compute/docs/gpus/gpu-regions-zones) for suitable region and zone with compatible GPU. Those are available [regions & zones](https://cloud.google.com/compute/docs/regions-zones)
1. [About GKE modes of operation](https://cloud.google.com/kubernetes-engine/docs/concepts/choose-cluster-mode) to choose b/w Autopilot (recommended) and Standard mode

#### GPU types
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

**Resource Guidelines**
- *System RAM*: Used for model loading, CPU computations, and vLLM framework overhead
- *PVC Storage*: Used for persistent model cache, avoiding re-downloads on pod restarts
- *GPU Memory*: Should be 1.5-2x the model size for optimal performance
- *Shared Memory (dshm)*: 2-8GB depending on model size and tensor parallel configuration

**Notes**
- For models >70B parameters, consider using tensor parallelism across multiple GPUs
- Quantized models (4-bit, 8-bit) require significantly less GPU memory
- Add 20-30% buffer to PVC storage for model updates and temporary files
- Monitor actual usage and adjust resources based on workload patterns
- Parameter counts are approximate and may vary between model variants

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Prepare environment (Ori + GKE)

From here, not that Ori does not need `$NAMESPACE`, while using `NAMESPACE` in GKE allowing easier control. E.g:
```bash
# Ori
kubectl apply -f <some-file>.yaml
# GKE
kubectl -n $NAMESPACE apply -f <some-file>.yaml
```

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


<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Create & connect a GKE cluster (GKE only)

1. Create cluster: Select select 1 mode to create cluster (Check [cluster create cmd doc](https://cloud.google.com/sdk/gcloud/reference/container/clusters/create) for detail)

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

1. Connect to cluster
    ```bash
    gcloud container clusters get-credentials $CLUSTER_NAME \
        --location=$REGION
    ```

1. Create namespace
    ```bash
    kubectl create namespace "$NAMESPACE" || true

    # Optionally set the default namespace for this context
    kubectl config set-context --current --namespace="$NAMESPACE"
    ```

1. Verify cluster and namespace info
    ```bash
    # Verify context. Expect: "gke_<PROJECT_ID>_<REGION>_<CLUSTER_NAME>"
    kubectl config current-context

    # Quick check: is this an Autopilot cluster? Expect: "true" if use Autopilot
    gcloud container clusters describe $CLUSTER_NAME --region $REGION --format='value(autopilot.enabled)'

    # Check GPU
    # Should see no GPU now as there's no namespace using GPU
    kubectl get nodes -o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu

    # Get all namespaces:
    kubectl get namespaces
    ```

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Create secret for HF credentials (Ori + GKE)
1. Remember to add Hugging Face credentials to `hf_api_token` in `hf-token-secret.yaml` file.
    ```bash
    kubectl -n $NAMESPACE apply -f hf-token-secret.yaml
    ```
    OR
    ```bash
    kubectl -n $NAMESPACE create secret generic hf-secret \
        --from-literal=hf_api_token=${HF_TOKEN} \
        --dry-run=client -o yaml | kubectl -n "$NAMESPACE" apply -f -
    ```

1. Verify the secret was created
    ```bash
    kubectl -n $NAMESPACE get secrets
    ```

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Persistent Volume Claim (PVC) (Ori + GKE)
This PVC is used to cache Hugging Face models for vLLM.

1. Create PVC: Remember to adjust storage requested in `<pvc-file>.yaml` (E.g. `vllm-pvc.yaml`) according to model size.
    ```bash
    kubectl -n $NAMESPACE apply -f <pvc-file>.yaml
    ```

1. Check PVC status: Get details and troubleshoot (E.g. `<pvc-metadata.name>` is `vllm-models` from `./Ori/vllm-pvc.yaml`):
    ```bash
    kubectl -n $NAMESPACE describe pvc <pvc-file.metadata:name>
    ```

1. (Optional) Check that the PVC is **Bound** after deploying below:
    ```bash
    kubectl -n $NAMESPACE get pvc
    ```

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Deploy LLM (Ori + GKE)
The deployment cmd will launch the vLLM server with GPU support and mount the model cache PVC.

```bash
kubectl -n $NAMESPACE apply -f <deployment-file>.yaml
```

### Check status

1. Check ready: Wait until "get pods" shows READY=1/1 and STATUS=Running.
    ```bash
    kubectl -n $NAMESPACE get pods -o wide
    kubectl -n $NAMESPACE get pods -w
    kubectl -n $NAMESPACE describe pod -l app=qwen3-server | sed -n '/Events/,$p'
    ```

1. View the logs from the running Deployment. E.g: `<template:metadata:labels:app>`=`qwen3-server` from `./GKE/vllm-qwen3-32b.yaml` OR `<metadata:name>`=`vllm-server` from `./Ori/vllm-deployment.yaml`.
    ```bash
    # Recommend:
    kubectl -n $NAMESPACE logs -f -l app=<template:metadata:labels:app>
    # OR vllm-server is metadata.name
    kubectl -n $NAMESPACE logs deployment/<metadata:name>
    ```

1. Check for model download progress. E.g: `<metadata:name>`=`vllm-qwen3-deployment` from `./GKE/vllm-qwen3-32b.yaml`
    ```bash
    kubectl -n $NAMESPACE exec -it deploy/<metadata:name> -- bash -lc 'du -sh /root/.cache/huggingface 2>/dev/null || true; ls -lh /root/.cache/huggingface/hub 2>/dev/null || true'
    ```

**Note**:
1. If the pod is stuck in `Pending` or `ContainerCreating`, see [Troubleshooting](#troubleshooting-ori--gke) below.

### Check GPU usage
```bash
kubectl get nodes -L cloud.google.com/gke-accelerator \
  -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu

# OR Check if GPU nodes are available
kubectl get nodes -o wide
# Verify GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Expose the vLLM Service (Ori + GKE)
Create service -> expose model to specific port depending on method.

Important endpoints:
1. **vLLM API**: `http://<vLLM-IP-ADDR>:8000`
1. **vLLM Metrics**: `http://<vLLM-IP-ADDR>:8000/metrics`

**Note**:
- `<vLLM-IP-ADDR>`: is `<EXTERNAL-IP>` (LoadBalancer) or `127.0.0.1` (forwardPort)

### LoadBalancer Service (recommend)
The LoadBalancer service automatically creates an external IP. Check the service status:
1. Ensure service selector match:
    - `<spec:selector>` from `<service-file>.yaml` must match with `<selector:matchLabels>` from `<deployment-file>.yaml`.
    - E.g:
        ```bash
        # In ./GKE/vllm-service.yaml:
        spec:
            selector:
                app: gemma-server

        # In ./GKE/vllm-gemma-3-1b-it.yaml:
        spec:
            selector:
                matchLabels:
                app: gemma-server
        ```

1. Apply the service:
    ```bash
    kubectl -n $NAMESPACE apply -f vllm-service.yaml
    ```
1. Verify working. E.g. `<metadata:name>`=`vllm-server` from `./Ori/vllm-service.yaml`:
    ```bash
    kubectl -n $NAMESPACE get svc <metadata:name> -o wide
    ```
    This also shows external IP address. Expect address under `EXTERNAL-IP` column:
    - If `EXTERNAL-IP` is assigned, you can access the API from outside the cluster.
    - If not, or for local testing, use port-forwarding below.

1. Test with a question. In a **new terminal**, run:
    ```bash
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

    curl http://<EXTERNAL-IP>:8000/metrics
    ```

### Port-Forward for Local/Internal Access
Your Service is ClusterIP, so it’s only reachable inside the cluster. kubectl port-forward service/llm-service 8000:8000 creates a temporary local tunnel so you can test the API at http://127.0.0.1:8000 from your Cloud Shell or laptop.

1. Forward port:
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
        ],
        "temperature": 0
    }'

    curl http://127.0.0.1:8000/metrics
    ```
<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Monitoring Services (Ori + GKE)

### Update Prometheus Configuration
Update `./Monitoring/prometheus-deployment.yaml` (if use K8s) OR `./Monitoring/prometheus_grafana/prometheus.yaml` (if use Docker) using either approaches below:

1. Update based on vLLM service IP address:
    ```yaml
    scrape_configs:
    - job_name: vllm
        static_configs:
        - targets:
            - '<vLLM-IP-ADDR>:8000'  # Replace with <EXTERNAL-IP> OR *127.0.0.1*
    ```

1. OR Update based on metadata (`<metadata:name>`):
    ```yaml
    # In ./GKE/vllm-service.yaml
    metadata:
        name: vllm-service

    # In ./Monitoring/prometheus-deployment.yaml
    scrape_configs:
    - job_name: vllm-k8s
        static_configs:
        - targets:
            - '<metadata:name>:8000' # Replace with *vllm-service*
    ```

### Deployment
There are 2 approaches. Recommend ***Kubernetes-Native*** for Production

#### Kubernetes-Native
1. Deploy Grafana+Prometheus in `./Monitoring/`:
    ```bash
    # Deploy Prometheus
    kubectl -n $NAMESPACE apply -f prometheus-deployment.yaml

    # Deploy Grafana
    kubectl -n $NAMESPACE apply -f grafana-deployment.yaml
    ```

1. (Optional) Wait for monitoring services to be ready
    ```bash
    kubectl -n $NAMESPACE wait --for=condition=available --timeout=300s deployment/prometheus
    kubectl -n $NAMESPACE wait --for=condition=available --timeout=300s deployment/grafana
    ```

1. Verify working
    ```bash
    # Verify Prometheus
    kubectl -n $NAMESPACE get svc prometheus -o wide
    
    # Verify Grafana
    kubectl -n $NAMESPACE get svc grafana -o wide
    ```

#### Docker Compose

1. Deploy Grafana+Prometheus in `./Monitoring/prometheus_grafana/`
    ```bash
    cd prometheus_grafana
    docker-compose up -d
    ```

1. Verify working
    ```bash
    # For Docker Compose approach
    docker-compose -f prometheus_grafana/docker-compose.yaml ps
    ```

### Access Monitoring Services

To get external IPs, run:
```bash
kubectl -n $NAMESPACE get svc -o wide
```
Here are URLs:
- Prometheus:
    - Kubernetes: `http://<prometheus-EXTERNAL-IP>:9090`
    - Docker: `http://localhost:9090`
- Grafana:
    - Kubernetes: `http://<grafana-EXTERNAL-IP>:3000`
    - Docker: `http://localhost:3000`

### Setting Up Grafana Dashboard
1. Open your browser and go to the Grafana URL (`http://<grafana-EXTERNAL-IP>:3000`)
1. Login with:
   - Username: `admin`
   - Password: `admin`
1. (Optional) Update password: SKIP
1. Go to **Dashboards** -> **New** -> **Import**
1. Click **Upload JSON file**. Select the `prometheus_grafana/grafana.json` file
1. Click **Load**
1. Now the **Dashboards** should show new Dashboard you have just imported:
    1. Click that Dashboard
    1. Select **Prometheus** for `datasource`
    1. Select **hf/model/name** for `model_name`

### Configure Monitor Dashboard
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

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

## Testing the LLM (Ori + GKE)
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

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>


## Clean Up (Ori + GKE)

1. To remove all vLLM resources:
    - Remove Docker Compose (if use):
        ```bash
        cd prometheus_grafana
        docker-compose down
        ```
    - Remove on K8s:
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

1. Delete Any Remaining Pods or Services
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

1. (Optional) Delete PVCs and Secrets
    If you created any other PVCs or secrets:
    ```bash
    kubectl get pvc
    kubectl delete pvc <pvc-name>

    kubectl get secrets
    kubectl delete secret <secret-name>
    ```

1. Clean Up LoadBalancer:
    The LoadBalancer service is automatically cleaned up when you delete the service. No manual cleanup needed.

1. Delete GKE Cluster
    ```bash
    gcloud container clusters delete $CLUSTER_NAME \
        --zone=$ZONE
    ```

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>


## Troubleshooting (Ori + GKE)

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

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>

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

### Option 2: Docker Compose
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

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>


## References

- [GKE] [Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE] [GPU Support](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [GKE] [Kubernetes GPU Support](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [GKE] [Storage Classes](https://cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes)
- [GKE] Tutorial: [Serve Llama models using GPUs on GKE with vLLM](https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-llama-gpus-vllm)
- [GKE] Tutorial: [Serve Gemma open models using GPUs on GKE with vLLM](https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm)
- [GKE] Request GPU: [request-gpus](https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus)
- [vLLM] [Documentation](https://docs.vllm.ai/)
- [vLLM] [Engine Args](https://docs.vllm.ai/en/latest/configuration/engine_args.html)
- [vLLM] [Kubernetes Deployment Guide](https://docs.vllm.ai/en/stable/deployment/k8s.html#deployment-with-gpus)
- [Ori] [Stable Diffusion Kubernetes Example](https://docs.ori.co/kubernetes/examples/stable-diffusion/)
- [Hugging Face] [Private Models](https://huggingface.co/docs/hub/security-tokens)

<div align="right">[<a href="#vllm-deployment-guide-using-k8s">Back to Top</a>]</div>
