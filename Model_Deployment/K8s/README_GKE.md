# Deploy vLLM on Google Kubernetes Engine (GKE)

This guide walks you through deploying the vLLM model on Google Kubernetes Engine (GKE) with GPU support, highlighting the key differences from Ori's cluster deployment.

---

## Table of Contents
- [Available GKE Files](#available-gke-files)
- [Key Differences from Ori's Cluster](#key-differences-from-oris-cluster)
- [GKE Cluster Setup](#gke-cluster-setup)
- [Updated Deployment Files](#updated-deployment-files)
- [Service Access Options](#service-access-options)
- [Deployment Steps](#deployment-steps)
- [GKE-Specific Considerations](#gke-specific-considerations)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Available GKE Files

The following GKE-specific YAML files are available in the `kubernetes/` directory:

### **Core Deployment Files:**
- **`vllm-pvc-gke.yaml`** - PersistentVolumeClaim with GKE storage class
- **`vllm-deployment-mistral-7b-gke.yaml`** - Deployment for Mistral-7B model
- **`vllm-deployment-gke.yaml`** - Deployment for basic models (opt-125m)
- **`vllm-service-gke.yaml`** - LoadBalancer service for simple external access (recommended)
- **`vllm-service-internal-gke.yaml`** - ClusterIP service for internal access only

### **Key Changes from Original Files:**
- Node selectors removed for GKE compatibility
- Storage class updated to `pd-ssd`
- Service type changed to `LoadBalancer` for simple external access (Google Cloud recommended)
- Alternative internal service available for secure deployments

---

## Key Differences from Ori's Cluster

### 1. **Node Selector Changes**
- **Ori's Cluster**: Uses specific GPU node selector `gpu.nvidia.com/class: L40S`
- **GKE**: Different GPU node pools and labeling schemes, may require removing/modifying node selectors

### 2. **GPU Resource Management**
- **Ori's Cluster**: Uses `nvidia.com/gpu` resource specification
- **GKE**: May require `cloud.google.com/gke-accelerator` or different GPU resource specifications
- **GKE GPU Types**: T4, V100, A100, etc. (different from L40S)

### 3. **Storage Class Differences**
- **Ori's Cluster**: Uses default storage class
- **GKE**: Different default storage classes, may need explicit specification (e.g., `standard`, `premium-rwo`, `pd-ssd`)

### 4. **LoadBalancer Service Type**
- **Ori's Cluster**: LoadBalancer creates cluster-specific load balancer
- **GKE**: LoadBalancer creates Google Cloud Load Balancer, exposes to internet
- **Recommendation**: Use LoadBalancer for simplicity (Google Cloud recommended) or ClusterIP for internal access only

---

## GKE Cluster Setup

### 1. **Create GKE Cluster with GPU Support**
```bash
# Create a GKE cluster with GPU nodes
gcloud container clusters create vllm-cluster \
  --zone=us-central1-a \
  --machine-type=n1-standard-4 \
  --accelerator type=nvidia-tesla-t4,count=1 \
  --num-nodes=1 \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=3

# Get credentials for the cluster
gcloud container clusters get-credentials vllm-cluster --zone=us-central1-a
```

### 2. **Install NVIDIA GPU Operator**
GKE requires the NVIDIA GPU operator for proper GPU support:
```bash
kubectl create -f https://raw.githubusercontent.com/NVIDIA/k8s-device-plugin/master/nvidia-device-plugin.yml
```

### 3. **Verify GPU Nodes**
```bash
# Check if GPU nodes are available
kubectl get nodes -o wide

# Verify GPU resources
kubectl describe nodes | grep -A 10 "Allocated resources"
```

---

## Updated Deployment Files

### 1. **Updated PVC for GKE**
The GKE-specific PVC file is located at `kubernetes/vllm-pvc-gke.yaml` and includes:
- `pd-ssd` storage class for better performance
- 5Gi storage allocation
- ReadWriteOnce access mode

**File**: `kubernetes/vllm-pvc-gke.yaml`

### 2. **Updated Deployment for GKE**

**For Mistral-7B Model**: `kubernetes/vllm-deployment-mistral-7b-gke.yaml`
- Includes shared memory configuration for tensor parallel inference
- GPU resource limits and requests configured
- Health checks and readiness probes
- Node selector removed for GKE compatibility

**For Basic Model (opt-125m)**: `kubernetes/vllm-deployment-gke.yaml`
- Simplified deployment for smaller models
- Basic GPU resource configuration
- Model cache volume mounting

### 3. **Updated Service for GKE**

**Primary Service (Recommended)**: `kubernetes/vllm-service-gke.yaml`
- LoadBalancer type for simple external access (Google Cloud recommended)
- Exposes vLLM API on port 8000
- Automatically creates Google Cloud Load Balancer

**Alternative Internal Service**: `kubernetes/vllm-service-internal-gke.yaml`
- ClusterIP type for internal access only
- More secure for production environments
- Requires port-forwarding or Ingress for external access

---

## Quick Start

**For a quick deployment, run these commands in order:**

```bash
# 1. Set up GKE context
gcloud container clusters get-credentials vllm-cluster --zone=us-central1-a

# 2. Create PVC
kubectl apply -f kubernetes/vllm-pvc-gke.yaml

# 3. Deploy vLLM (choose one)
kubectl apply -f kubernetes/vllm-deployment-mistral-7b-gke.yaml
# OR for basic model
# kubectl apply -f kubernetes/vllm-deployment-gke.yaml

# 4. Create service
kubectl apply -f kubernetes/vllm-service-gke.yaml

# 5. Set up Ingress (optional, for external access)
# kubectl apply -f kubernetes/vllm-ingress-gke.yaml
```

---

## Deployment Steps

### 1. **Set Up GKE Context**
```bash
# Ensure you're using the correct GKE cluster
gcloud container clusters get-credentials vllm-cluster --zone=us-central1-a

# Verify context
kubectl config current-context
```

### 2. **Create the PersistentVolumeClaim (PVC)**
```bash
kubectl apply -f kubernetes/vllm-pvc-gke.yaml
```

Check that the PVC is **Bound**:
```bash
kubectl get pvc
```

If not bound, troubleshoot with:
```bash
kubectl describe pvc vllm-models
```

### 3. **Deploy the vLLM Model Server**

**For Mistral-7B Model:**
```bash
kubectl apply -f kubernetes/vllm-deployment-mistral-7b-gke.yaml
```

**For Basic Model (opt-125m):**
```bash
kubectl apply -f kubernetes/vllm-deployment-gke.yaml
```

Check pod status:
```bash
kubectl get pods -o wide
```

Wait until the pod status is `Running` and `READY` is `1/1`.

### 4. **Expose the vLLM Service**
```bash
kubectl apply -f kubernetes/vllm-service-gke.yaml
```

### 5. **Access the vLLM Service**

**With LoadBalancer Service (Automatic):**
The LoadBalancer service automatically creates an external IP. Check the service status:
```bash
kubectl get svc vllm-server
```
Look for the `EXTERNAL-IP` column to get your external IP address.

**Alternative: Port-Forward for Local Access**
If you prefer internal access or are using the internal service:
```bash
kubectl port-forward deployment/vllm-server 8000:8000
```

### 6. **Port-Forward for Local Access (Alternative)**
If you prefer not to use external LoadBalancer:
```bash
kubectl port-forward deployment/vllm-server 8000:8000
```

### 7. **Test the vLLM API**
```bash
# If using LoadBalancer service, use the external IP
curl http://<EXTERNAL-IP>/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "prompt": "San Francisco is a",
        "max_tokens": 7,
        "temperature": 0
      }'

# If using port-forward, use localhost
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "mistralai/Mistral-7B-Instruct-v0.3",
        "prompt": "San Francisco is a",
        "max_tokens": 7,
        "temperature": 0
      }'
```

---

## Service Access Options

Based on [Google Cloud's vLLM tutorial](https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm), here are the recommended approaches:

### **1. LoadBalancer Service (Recommended - Simplest)**
- **File**: `kubernetes/vllm-service-gke.yaml`
- **Pros**: Automatic external access, no additional configuration needed
- **Cons**: Exposes service to internet
- **Use Case**: Development, testing, public APIs
- **Google Cloud Recommendation**: ✅ Primary approach for vLLM deployments

### **2. ClusterIP Service (Internal Access)**
- **File**: `kubernetes/vllm-service-internal-gke.yaml`
- **Pros**: More secure, internal cluster access only
- **Cons**: Requires port-forwarding or Ingress for external access
- **Use Case**: Production environments, secure deployments
- **Access Method**: `kubectl port-forward` or Ingress

### **3. Port Forwarding (Development)**
- **Command**: `kubectl port-forward deployment/vllm-server 8000:8000`
- **Pros**: Simple, secure, no external exposure
- **Cons**: Single-user access, manual setup required
- **Use Case**: Local development, testing

---

## GKE-Specific Considerations

### 1. **Resource Quotas**
GKE has different resource quotas. Check your cluster limits:
```bash
kubectl describe resourcequota
```

### 2. **GPU Node Pool Management**
```bash
# Scale GPU node pool
gcloud container clusters resize vllm-cluster \
  --zone=us-central1-a \
  --node-pool=default-pool \
  --num-nodes=2

# Enable autoscaling for GPU nodes
gcloud container node-pools update default-pool \
  --cluster=vllm-cluster \
  --zone=us-central1-a \
  --enable-autoscaling \
  --min-nodes=1 \
  --max-nodes=5
```

### 3. **Cost Optimization**
- Use preemptible nodes for cost savings (not recommended for production)
- Monitor GPU utilization with Cloud Monitoring
- Set up billing alerts

### 4. **Security Best Practices**
- Use IAM roles instead of service accounts
- Enable Workload Identity
- Restrict network access with VPC and firewall rules

---

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

---

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

---

## References

- [GKE Documentation](https://cloud.google.com/kubernetes-engine/docs)
- [GKE GPU Support](https://cloud.google.com/kubernetes-engine/docs/how-to/gpus)
- [vLLM Documentation](https://docs.vllm.ai/)
- [Kubernetes GPU Support](https://kubernetes.io/docs/tasks/manage-gpus/scheduling-gpus/)
- [GKE Storage Classes](https://cloud.google.com/kubernetes-engine/docs/concepts/persistent-volumes)

---

## Migration Checklist

- [ ] Set up GKE cluster with GPU support
- [ ] Install NVIDIA GPU operator
- [ ] Update deployment files for GKE compatibility
- [ ] Remove/modify node selectors
- [ ] Update storage class specifications
- [ ] Choose LoadBalancer (simple) or ClusterIP (secure) service
- [ ] Test deployment and API access
- [ ] Configure monitoring and logging
- [ ] Set up security policies
- [ ] Document GKE-specific configurations
