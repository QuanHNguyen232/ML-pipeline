https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-llama-gpus-vllm#llama-4-maverick-17b-128e

USING NVIDIA-L4
https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm#autopilot

https://cloud.google.com/compute/docs/gpus/gpu-regions-zones

Request GPU in GKE: https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus

## Prepare environment
gcloud config set project venerian
gcloud config set billing/quota_project venerian
export PROJECT_ID=$(gcloud config get project)
export REGION=us-central1
export ZONE=us-central1-a
export CONTROL_PLANE_LOCATION=us-central1
export CLUSTER_NAME=venera-test
export VLLM_LOGGING_LEVEL=DEBUG
export NAMESPACE=llm

## Create a GKE cluster and node pool
1. (autopilot mode)
Link: https://cloud.google.com/sdk/gcloud/reference/container/clusters/create
<!-- gcloud container clusters create-auto $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --release-channel=rapid -->
gcloud container clusters create-auto $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --location=$CONTROL_PLANE_LOCATION \
    --release-channel=rapid
2. Standard:
gcloud container clusters create $CLUSTER_NAME \
    --project=$PROJECT_ID \
    --region=$REGION \
    --machine-type g2-standard-8 \
    --accelerator type=nvidia-l4,count=1 \
    --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
## Connect to cluster
```bash
gcloud container clusters get-credentials $CLUSTER_NAME \
    --location=$REGION
```

## Create namespace
kubectl create namespace "$NAMESPACE" || true

## Checking info
Quick check: is this an Autopilot cluster?
```bash
gcloud container clusters describe $CLUSTER_NAME --region $REGION --format='value(autopilot.enabled)'
# Expect: true for Autopilot
```
Check GPU:
kubectl get nodes -o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu

Get all namespaces:
kubectl get namespaces

## Create a Kubernetes secret for Hugging Face credentials
kubectl create secret generic hf-secret \
    --from-literal=hf_api_token=${HF_TOKEN} \
    --dry-run=client -o yaml | kubectl apply -f -
OR
kubectl apply -f hf-token-secret.yaml

## Create PVC
kubectl apply -f vllm-pvc-gke.yaml

## Deploy
kubectl apply -f vllm-deployment-mistral-7b-gke.yaml

## Check deployment status
kubectl -n llm get pods -o wide
kubectl -n llm get pods -w
kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'

View the logs from the running Deployment:
kubectl -n llm logs -f -l app=gemma-server

# Now GPU should be shown:
kubectl get nodes -L cloud.google.com/gke-accelerator \
  -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu


## test
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