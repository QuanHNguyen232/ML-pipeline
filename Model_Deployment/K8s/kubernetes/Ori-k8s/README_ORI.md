# Deploy vLLM on Kubernetes (GPU)

This guide walks you through deploying the vLLM model (e.g., `facebook/opt-125m`) on a Kubernetes cluster with GPU support, using the provided YAML files.

---

## Table of Contents
- [Public Model Deployment](#deploy-vllm-on-kubernetes-gpu)
- [Private Model Deployment](#deploy-private-vllm-model-on-kubernetes-gpu)
- [Troubleshooting](#troubleshooting)
- [References](#references)

---

## Public Model Deployment

### 1. Set Up Kubeconfig
This `kubeConfig.yaml` file can be downloaded from Ori after creating a K8S cluster
```bash
export KUBECONFIG=./kubernetes/kubeConfig.yaml
```

### 2. Create the PersistentVolumeClaim (PVC)
This PVC is used to cache Hugging Face models for vLLM.

Apply the PVC manifest:
```bash
kubectl apply -f kubernetes/vllm-pvc.yaml
```
Check that the PVC is **Bound**:
```bash
kubectl get pvc
```
If not bound, troubleshoot with:
```bash
kubectl describe pvc vllm-models
```

### 3. Deploy the vLLM Model Server
The deployment manifest will launch the vLLM server with GPU support and mount the model cache PVC.

Apply the deployment:
```bash
kubectl apply -f kubernetes/vllm-deployment.yaml
```
Check pod status:
```bash
kubectl get pods -o wide
```
Wait until the pod status is `Running` and `READY` is `1/1`.

If the pod is stuck in `Pending` or `ContainerCreating`, see Troubleshooting below.

### 4. Expose the vLLM Service
The service manifest exposes the vLLM server on port 8000 (as a LoadBalancer by default).

Apply the service:
```bash
kubectl apply -f kubernetes/vllm-service.yaml
```
Check the service:
```bash
kubectl get svc vllm-server
```
- If `EXTERNAL-IP` is assigned, you can access the API from outside the cluster.
- If not, or for local testing, use port-forwarding below.

### 5. Port-Forward for Local Access (Optional)
If you want to access the API from your local machine:
```bash
kubectl port-forward deployment/vllm-server 8000:8000
```
You should see:
```
Forwarding from 127.0.0.1:8000 -> 8000
```

### 6. Test the vLLM API
In a new terminal, run:
```bash
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "facebook/opt-125m",
        "prompt": "San Francisco is a",
        "max_tokens": 7,
        "temperature": 0
      }'
```
You should receive a JSON response with the model's completion.

### 7. Monitor Logs
To view server logs:
```bash
kubectl logs deployment/vllm-server
```

### 8. Clean Up
1. To remove all vLLM resources:
```bash
kubectl delete -f kubernetes/vllm-deployment.yaml
kubectl delete -f kubernetes/vllm-service.yaml
kubectl delete -f kubernetes/vllm-pvc.yaml
```

2. Delete Any Remaining Pods or Services
If you want to ensure everything is gone, you can list and delete all pods and services in the default namespace:
```bash
kubectl get pods
kubectl get svc
```
Then, for any remaining resources:
```bash
kubectl delete pod <pod-name>
kubectl delete svc <service-name>
```

3. (Optional) Delete PVCs and Secrets
If you created any other PVCs or secrets:
```bash
kubectl get pvc
kubectl delete pvc <pvc-name>

kubectl get secrets
kubectl delete secret <secret-name>
```

---

## Private Model Deployment

This section covers deploying a private Hugging Face model using vLLM on Kubernetes with GPU support.

### 1. Set Up Hugging Face Token Secret
First, create a secret containing your Hugging Face access token to authenticate with private models:

```bash
# Edit the token in the secret file
# Replace "REPLACE_WITH_YOUR_ACTUAL_HF_TOKEN" with your actual token
kubectl apply -f kubernetes/hf-token-secret.yaml
```

**Important:** Before applying, edit `kubernetes/hf-token-secret.yaml` and replace `REPLACE_WITH_YOUR_ACTUAL_HF_TOKEN` with your actual Hugging Face token.

Verify the secret was created:
```bash
kubectl get secrets
```

### 2. Create the PersistentVolumeClaim (PVC)
This PVC is used to cache Hugging Face models for vLLM.

Apply the PVC manifest:
```bash
kubectl apply -f kubernetes/vllm-pvc.yaml
```
Check that the PVC is **Bound**:
```bash
kubectl get pvc
```

### 3. Deploy the Private vLLM Model Server
The private model deployment manifest will launch the vLLM server with GPU support, mounted model cache PVC, and Hugging Face authentication.

**Before applying, edit the deployment file:**
- In `kubernetes/vllm-deployment-private-model.yaml`, replace `YOUR_PRIVATE_MODEL_NAME` with your actual private model name (e.g., `your-username/your-model-name`)

Apply the deployment:
```bash
kubectl apply -f kubernetes/vllm-deployment-private-model.yaml
```
Check pod status:
```bash
kubectl get pods -o wide
```
Wait until the pod status is `Running` and `READY` is `1/1`.

### 4. Expose the Private vLLM Service
The service manifest exposes the private vLLM server on port 8000.

Apply the service:
```bash
kubectl apply -f kubernetes/vllm-service-private-model.yaml
```
Check the service:
```bash
kubectl get svc vllm-server-private
```

### 5. Port-Forward for Local Access (Optional)
If you want to access the API from your local machine:
```bash
kubectl port-forward deployment/vllm-server-private 8000:8000
```
You should see:
```
Forwarding from 127.0.0.1:8000 -> 8000
```

### 6. Test the Private vLLM API
In a new terminal, run:
```bash
curl http://localhost:8000/v1/completions \
  -H "Content-Type: application/json" \
  -d '{
        "model": "YOUR_PRIVATE_MODEL_NAME",
        "prompt": "Hello, how are you?",
        "max_tokens": 50,
        "temperature": 0.7
      }'
```
**Note:** Replace `YOUR_PRIVATE_MODEL_NAME` with your actual private model name.

### 7. Monitor Logs
To view server logs:
```bash
kubectl logs deployment/vllm-server-private
```

### 8. Clean Up Private Model Resources
1. To remove all private vLLM resources:
```bash
kubectl delete -f kubernetes/vllm-deployment-private-model.yaml
kubectl delete -f kubernetes/vllm-service-private-model.yaml
kubectl delete -f kubernetes/vllm-pvc.yaml
kubectl delete -f kubernetes/hf-token-secret.yaml
```

2. Delete Any Remaining Pods or Services:
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

---

## Troubleshooting

### Pod Stuck in Pending
- **PVC not bound:** Ensure you applied the PVC and it is `Bound` (`kubectl get pvc`).
- **No available GPU:** Make sure no other pods are using the GPU, and your node has available GPU resources.
- **Node selector mismatch:** The deployment uses `nodeSelector: gpu.nvidia.com/class: L40S`. Ensure your node has this label.

### Pod Stuck in ContainerCreating
- **Image pulling:** The node may be downloading the Docker image. This can take several minutes on a fresh node.
- **PVC mounting:** Wait for the PVC to attach. If it fails, check `kubectl describe pod <pod-name>` for errors.

### Service Not Accessible
- **No EXTERNAL-IP:** Use port-forwarding for local access.
- **Port-forward fails:** Ensure the pod is `Running` and listening on port 8000.

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

---

## References
- [vLLM Kubernetes Deployment Guide](https://docs.vllm.ai/en/stable/deployment/k8s.html#deployment-with-gpus)
- [Ori Stable Diffusion Kubernetes Example](https://docs.ori.co/kubernetes/examples/stable-diffusion/)
- [Hugging Face Private Models](https://huggingface.co/docs/hub/security-tokens)
