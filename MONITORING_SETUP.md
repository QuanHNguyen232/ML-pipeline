# vLLM Monitoring Setup Guide

This guide will help you set up monitoring for your vLLM OPT-125m deployment using Prometheus and Grafana.

## Prerequisites

1. **Kubernetes Cluster**: Make sure you have a Kubernetes cluster running (Docker Desktop with Kubernetes, minikube, or any other cluster)
2. **kubectl**: Install and configure kubectl to connect to your cluster
3. **GPU Support**: Ensure your cluster has GPU support if you're using GPU resources
4. **Docker & Docker Compose**: For the Docker Compose approach (Option 2)

## Two Setup Options

### Option 1: Kubernetes-Native Monitoring (Recommended for Production)

This approach runs everything in Kubernetes, following the same pattern as your vLLM deployment.

**For Windows (PowerShell):**
```powershell
.\setup-monitoring.ps1
```

**For Linux/Mac (Bash):**
```bash
chmod +x setup-monitoring.sh
./setup-monitoring.sh
```

### Option 2: Docker Compose Monitoring (Following Original README.md)

This approach follows the original vLLM documentation, running Prometheus and Grafana in Docker while your vLLM runs in Kubernetes.

**For Windows (PowerShell):**
```powershell
.\setup-monitoring-docker.ps1
```

**For Linux/Mac (Bash):**
```bash
chmod +x setup-monitoring-docker.sh
./setup-monitoring-docker.sh
```

## Manual Setup Instructions

### Option 1: Kubernetes-Native Setup

#### Step 1: Deploy vLLM Application

```bash
# Deploy the PVC for model storage
kubectl apply -f kubernetes/vllm-pvc.yaml

# Deploy the vLLM server
kubectl apply -f kubernetes/vllm-deployment.yaml

# Create the service
kubectl apply -f kubernetes/vllm-service.yaml

# Wait for deployment to be ready
kubectl wait --for=condition=available --timeout=300s deployment/vllm-server
```

#### Step 2: Deploy Monitoring Stack

```bash
# Deploy Prometheus
kubectl apply -f kubernetes/prometheus-deployment.yaml

# Deploy Grafana
kubectl apply -f kubernetes/grafana-deployment.yaml

# Wait for monitoring services to be ready
kubectl wait --for=condition=available --timeout=300s deployment/prometheus
kubectl wait --for=condition=available --timeout=300s deployment/grafana
```

### Option 2: Docker Compose Setup (Following README.md)

#### Step 1: Deploy vLLM in Kubernetes

```bash
# Deploy vLLM in Kubernetes
kubectl apply -f kubernetes/vllm-pvc.yaml
kubectl apply -f kubernetes/vllm-deployment.yaml
kubectl apply -f kubernetes/vllm-service.yaml

# Wait for deployment to be ready
kubectl wait --for=condition=available --timeout=300s deployment/vllm-server
```

#### Step 2: Get vLLM External IP

```bash
# Get the external IP
kubectl get svc vllm-server -o wide

# If using port-forward (for local development)
kubectl port-forward svc/vllm-server 8000:8000
```

#### Step 3: Update Prometheus Configuration

Edit `prometheus_grafana/prometheus.yaml` and replace `host.docker.internal:8000` with your vLLM service IP:

```yaml
scrape_configs:
  - job_name: vllm
    static_configs:
      - targets:
          - 'YOUR_VLLM_IP:8000'  # Replace with your vLLM IP
```

#### Step 4: Start Monitoring with Docker Compose

```bash
cd prometheus_grafana
docker-compose up -d
```

## Verification

### Check All Services

```bash
# For Kubernetes-native approach
kubectl get svc

# For Docker Compose approach
docker-compose -f prometheus_grafana/docker-compose.yaml ps
```

### Check Pods (Kubernetes approach only)

```bash
kubectl get pods
```

All pods should be in `Running` status.

## Accessing the Services

### Option 1: Kubernetes-Native URLs

```bash
kubectl get svc -o wide
```

1. **vLLM API**: `http://<vllm-server-external-ip>:8000`
2. **vLLM Metrics**: `http://<vllm-server-external-ip>:8000/metrics`
3. **Prometheus**: `http://<prometheus-external-ip>:9090`
4. **Grafana**: `http://<grafana-external-ip>:3000`

### Option 2: Docker Compose URLs

1. **vLLM API**: `http://<vllm-server-external-ip>:8000`
2. **vLLM Metrics**: `http://<vllm-server-external-ip>:8000/metrics`
3. **Prometheus**: `http://localhost:9090`
4. **Grafana**: `http://localhost:3000`

## Setting Up Grafana Dashboard

### Step 1: Access Grafana

1. Open your browser and go to the Grafana URL
2. Login with:
   - Username: `admin`
   - Password: `admin`

### Step 2: Import vLLM Dashboard

1. Go to **Dashboards** → **Import**
2. Click **Upload JSON file**
3. Select the `prometheus_grafana/grafana.json` file
4. Click **Load**
5. Select **Prometheus** as the data source
6. Click **Import**

### Step 3: Configure Dashboard

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

## Testing the Setup

### Generate Load for Monitoring

You can test the monitoring by sending requests to your vLLM API:

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

### Check Metrics Endpoint

Visit `http://<vllm-server-external-ip>:8000/metrics` to see raw Prometheus metrics.

## Comparison: Kubernetes vs Docker Compose

| Aspect | Kubernetes-Native | Docker Compose |
|--------|------------------|----------------|
| **Deployment** | All in Kubernetes | vLLM in K8s, monitoring in Docker |
| **Management** | `kubectl` commands | `docker-compose` commands |
| **Scaling** | Kubernetes scaling | Manual scaling |
| **Networking** | Kubernetes services | Docker networking |
| **Storage** | Kubernetes volumes | Docker volumes |
| **Production** | ✅ Recommended | ⚠️ Development only |
| **Complexity** | Higher | Lower |

## Troubleshooting

### Common Issues

1. **Services not accessible**:
   - Check if LoadBalancer services have external IPs
   - For local development, consider using NodePort or port-forwarding

2. **Prometheus not scraping metrics**:
   - Verify vLLM service is running: `kubectl get pods -l app.kubernetes.io/name=vllm`
   - Check Prometheus targets: Go to Prometheus UI → Status → Targets
   - For Docker Compose: Check if vLLM IP is correctly configured

3. **Grafana can't connect to Prometheus**:
   - Verify Prometheus service is running
   - Check Grafana datasource configuration

### Useful Commands

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

## Cleanup

### Kubernetes-Native Cleanup

```bash
kubectl delete -f kubernetes/grafana-deployment.yaml
kubectl delete -f kubernetes/prometheus-deployment.yaml
kubectl delete -f kubernetes/vllm-service.yaml
kubectl delete -f kubernetes/vllm-deployment.yaml
kubectl delete -f kubernetes/vllm-pvc.yaml
```

### Docker Compose Cleanup

```bash
cd prometheus_grafana
docker-compose down
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