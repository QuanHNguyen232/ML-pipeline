#!/bin/bash

echo "🚀 Setting up vLLM Monitoring Stack..."

# Step 1: Deploy vLLM Application
echo "📦 Deploying vLLM Application..."
kubectl apply -f kubernetes/vllm-pvc.yaml
kubectl apply -f kubernetes/vllm-deployment.yaml
kubectl apply -f kubernetes/vllm-service.yaml

# Wait for vLLM to be ready
echo "⏳ Waiting for vLLM deployment to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/vllm-server

# Step 2: Deploy Monitoring Stack
echo "📊 Deploying Prometheus..."
kubectl apply -f kubernetes/prometheus-deployment.yaml

echo "📈 Deploying Grafana..."
kubectl apply -f kubernetes/grafana-deployment.yaml

# Wait for monitoring services to be ready
echo "⏳ Waiting for monitoring services to be ready..."
kubectl wait --for=condition=available --timeout=300s deployment/prometheus
kubectl wait --for=condition=available --timeout=300s deployment/grafana

# Step 3: Get Service Information
echo "🔍 Getting service information..."
echo ""
echo "=== vLLM Service ==="
kubectl get svc vllm-server
echo ""
echo "=== Prometheus Service ==="
kubectl get svc prometheus
echo ""
echo "=== Grafana Service ==="
kubectl get svc grafana

echo ""
echo "✅ Setup complete!"
echo ""
echo "📋 Access URLs:"
echo "   vLLM API: http://<vllm-server-external-ip>:8000"
echo "   vLLM Metrics: http://<vllm-server-external-ip>:8000/metrics"
echo "   Prometheus: http://<prometheus-external-ip>:9090"
echo "   Grafana: http://<grafana-external-ip>:3000 (admin/admin)"
echo ""
echo "🔧 To get external IPs, run:"
echo "   kubectl get svc"
echo ""
echo "📊 To import the vLLM dashboard in Grafana:"
echo "   1. Go to http://<grafana-external-ip>:3000"
echo "   2. Login with admin/admin"
echo "   3. Go to Dashboards > Import"
echo "   4. Upload the grafana.json file from prometheus_grafana/"
echo "   5. Select Prometheus as the data source" 