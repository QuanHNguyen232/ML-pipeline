# Deploy vLLM on Kubernetes (GPU)

This guide walks you through deploying the vLLM model (e.g., `facebook/opt-125m`) on a Kubernetes cluster with GPU support, using the provided YAML files.

---

## 1. Set Up Kubeconfig
This `kubeConfig.yaml` file can be downloaded from Ori after creating a K8S cluster
```bash
export KUBECONFIG=./kubernetes/kubeConfig.yaml
```

---

## 2. Create the PersistentVolumeClaim (PVC)
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

---

## 3. Deploy the vLLM Model Server
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

---

## 4. Expose the vLLM Service
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

---

## 5. Port-Forward for Local Access (Optional)
If you want to access the API from your local machine:
```bash
kubectl port-forward deployment/vllm-server 8000:8000
```
You should see:
```
Forwarding from 127.0.0.1:8000 -> 8000
```

---

## 6. Test the vLLM API
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

---

## 7. Monitor Logs
To view server logs:
```bash
kubectl logs deployment/vllm-server
```

---

## 8. Clean Up
1. To remove all vLLM resources:
```bash
kubectl delete -f kubernetes/vllm-deployment.yaml
kubectl delete -f kubernetes/vllm-service.yaml
kubectl delete -f kubernetes/vllm-pvc.yaml
```

1. Delete Any Remaining Pods or Services
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

1. (Optional) Delete PVCs and Secrets
If you created any other PVCs or secrets:
```bash
kubectl get pvc
kubectl delete pvc <pvc-name>

kubectl get secrets
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
