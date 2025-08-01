#!/bin/bash

echo "🚀 Setting up vLLM Monitoring using Docker Compose (following README.md)..."

# Step 1: Deploy vLLM in Kubernetes (if not already deployed)
echo "📦 Deploying vLLM in Kubernetes..."
kubectl apply -f kubernetes/vllm-pvc.yaml
kubectl apply -f kubernetes/vllm-deployment.yaml
kubectl apply -f kubernetes/vllm-service.yaml

# Wait for vLLM to be ready
echo "⏳ Waiting for vLLM deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/vllm-server

# Step 2: Get vLLM external IP
echo "🔍 Getting vLLM service information..."
VLLM_IP=$(kubectl get svc vllm-server -o jsonpath='{.status.loadBalancer.ingress[0].ip}')
if [ -z "$VLLM_IP" ]; then
    echo "⚠️  LoadBalancer IP not available, using port-forward instead..."
    echo "   Run this in another terminal: kubectl port-forward svc/vllm-server 8000:8000"
    VLLM_IP="localhost"
fi

echo "✅ vLLM available at: http://$VLLM_IP:8000"

# Step 3: Update Prometheus config for the vLLM IP
echo "📝 Updating Prometheus configuration..."
sed "s/host.docker.internal:8000/$VLLM_IP:8000/g" prometheus_grafana/prometheus.yaml > prometheus_grafana/prometheus-local.yaml

# Step 4: Start monitoring with Docker Compose
echo "🐳 Starting Prometheus and Grafana with Docker Compose..."
cd prometheus_grafana

# Use the updated prometheus config
sed "s/prometheus.yaml:/prometheus-local.yaml:/g" docker-compose.yaml > docker-compose-local.yaml

echo "📊 Starting monitoring stack..."
docker-compose -f docker-compose-local.yaml up -d

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Access URLs:"
echo "   vLLM API: http://$VLLM_IP:8000"
echo "   vLLM Metrics: http://$VLLM_IP:8000/metrics"
echo "   Prometheus: http://localhost:9090"
echo "   Grafana: http://localhost:3000 (admin/admin)"
echo ""
echo "📊 To import the vLLM dashboard in Grafana:"
echo "   1. Go to http://localhost:3000"
echo "   2. Login with admin/admin"
echo "   3. Go to Dashboards > Import"
echo "   4. Upload the grafana.json file"
echo "   5. Select Prometheus as the data source"
echo ""
echo "🛑 To stop monitoring:"
echo "   cd prometheus_grafana && docker-compose -f docker-compose-local.yaml down" 