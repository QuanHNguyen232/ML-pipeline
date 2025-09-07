## Deploy Gemma on GKE Autopilot with NVIDIA L4 GPUs using vLLM

This guide shows how to deploy Gemma open models on Google Kubernetes Engine (GKE) Autopilot using NVIDIA L4 GPUs and serve them via vLLM's OpenAI-compatible API.

References:
- Serve Gemma on GKE with vLLM (Autopilot): `https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm#autopilot`
- Autopilot GPUs – Request GPUs in your containers: `https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus`

### Overview
- You will create a GKE Autopilot cluster (Autopilot manages nodes for you).
- You will deploy vLLM serving `google/gemma-3-4b-it` on an NVIDIA L4 GPU.
- You will expose vLLM via a ClusterIP Service and test with port-forwarding.

### Prerequisites
- A Google Cloud project with billing enabled.
- GPU quota for NVIDIA L4 in your chosen region. Request quota if needed.
- Google Cloud SDK (`gcloud`) and `kubectl`. Using Cloud Shell is recommended.

Quota note:
- For GKE Autopilot, ensure Compute Engine API quotas for NVIDIA L4 GPUs in your target region. You do not need Cloud Run Admin API GPU quotas; those apply to Cloud Run, not GKE. See: `https://cloud.google.com/kubernetes-engine/docs/how-to/autopilot-gpus#request-gpus` and `https://cloud.google.com/kubernetes-engine/docs/tutorials/serve-gemma-gpu-vllm#autopilot`.

### 1) Configure environment
Use Cloud Shell or a bash environment.

```bash
PROJECT_ID="YOUR_PROJECT_ID"
REGION="us-central1"        # Choose an L4-capable region
CLUSTER_NAME="gemma-autopilot"
NAMESPACE="llm"

gcloud config set project "$PROJECT_ID"
gcloud services enable container.googleapis.com compute.googleapis.com monitoring.googleapis.com
```

Optional: confirm GPU quota for L4 in your region in the Console (IAM & Admin → Quotas) and increase if necessary.

### 2) Create an Autopilot cluster
```bash
gcloud container clusters create-auto "$CLUSTER_NAME" --region "$REGION"
gcloud container clusters get-credentials "$CLUSTER_NAME" --region "$REGION"
kubectl create namespace "$NAMESPACE" || true
```

Notes:
- In Autopilot, you do not create GPU node pools. GPU nodes are provisioned automatically when a Pod requests GPUs.

### 3) (Optional) Create a Hugging Face token secret
If the model pull requires authentication, store the token in a secret and pass it to vLLM. Replace the token value as appropriate, or skip this step if not required.

```bash
kubectl -n "$NAMESPACE" create secret generic hf-token \
  --from-literal=HUGGING_FACE_HUB_TOKEN="YOUR_HF_TOKEN"
```

### 4) Create the vLLM Deployment and Service (requests NVIDIA L4)
Save as `vllm-gemma-l4.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: vllm-gemma
  labels:
    app: vllm-gemma
spec:
  replicas: 1
  selector:
    matchLabels:
      app: vllm-gemma
  template:
    metadata:
      labels:
        app: vllm-gemma
      annotations:
        # Autopilot GPU request (type and count). See Autopilot GPUs doc.
        workload.googleapis.com/accelerator: '{"type":"nvidia-l4","count":"1"}'
    spec:
      containers:
      - name: vllm
        image: vllm/vllm-openai:latest
        args: ["--model", "google/gemma-3-4b-it"]
        ports:
        - name: http
          containerPort: 8000
        env:
        - name: HUGGING_FACE_HUB_TOKEN
          valueFrom:
            secretKeyRef:
              name: hf-token
              key: HUGGING_FACE_HUB_TOKEN
              optional: true
        resources:
          requests:
            cpu: "4"
            memory: "16Gi"
          limits:
            cpu: "4"
            memory: "16Gi"
            nvidia.com/gpu: 1
---
apiVersion: v1
kind: Service
metadata:
  name: llm-service
  labels:
    app: vllm-gemma
spec:
  type: ClusterIP
  selector:
    app: vllm-gemma
  ports:
  - name: http
    port: 8000
    targetPort: 8000
```

Notes:
- The annotation `workload.googleapis.com/accelerator` requests an NVIDIA L4 in Autopilot, and `nvidia.com/gpu: 1` requests a single GPU. See the docs referenced above.
- You typically do not need tolerations for GPUs in Autopilot.

Apply the manifests:
```bash
kubectl -n "$NAMESPACE" apply -f vllm-gemma-l4.yaml
```

### 5) Wait for the model server to be ready
Downloading model weights can take a while on first start.

```bash
kubectl -n "$NAMESPACE" rollout status deployment/vllm-gemma --timeout=30m
kubectl -n "$NAMESPACE" get pods -o wide
kubectl -n "$NAMESPACE" logs -f deploy/vllm-gemma
```

Proceed when logs show that vLLM has started and the HTTP server is listening on port 8000.

### 6) Test locally with port-forward
```bash
kubectl -n "$NAMESPACE" port-forward service/llm-service 8000:8000
```

In a separate terminal, call the OpenAI-compatible endpoint:

```bash
curl http://127.0.0.1:8000/v1/chat/completions \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "model": "google/gemma-3-4b-it",
    "messages": [
      {"role": "user", "content": "Why is the sky blue?"}
    ]
  }'
```

You should receive a JSON response with the assistant's message.

### 7) (Optional) Deploy a simple Gradio chat UI
Save as `gradio.yaml` and adjust `MODEL_ID` if you changed the model name:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: gradio
  labels:
    app: gradio
spec:
  replicas: 1
  selector:
    matchLabels:
      app: gradio
  template:
    metadata:
      labels:
        app: gradio
    spec:
      containers:
      - name: gradio
        image: us-docker.pkg.dev/google-samples/containers/gke/gradio-app:v1.0.4
        resources:
          requests:
            cpu: "250m"
            memory: "512Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        env:
        - name: CONTEXT_PATH
          value: "/v1/chat/completions"
        - name: HOST
          value: "http://llm-service:8000"
        - name: LLM_ENGINE
          value: "openai-chat"
        - name: MODEL_ID
          value: "google/gemma-3-4b-it"
        ports:
        - containerPort: 7860
---
apiVersion: v1
kind: Service
metadata:
  name: gradio
spec:
  selector:
    app: gradio
  ports:
  - protocol: TCP
    port: 8080
    targetPort: 7860
  type: ClusterIP
```

Apply and access:
```bash
kubectl -n "$NAMESPACE" apply -f gradio.yaml
kubectl -n "$NAMESPACE" wait --for=condition=Available --timeout=900s deployment/gradio
kubectl -n "$NAMESPACE" port-forward service/gradio 8080:8080
```
Open `http://127.0.0.1:8080` in your browser.

### Troubleshooting
- Empty reply or 502/504: The model may still be downloading. Check logs until the server is ready.
- Image pull errors: Ensure public image access; try `imagePullPolicy: Always` if needed.
- GPU scheduling delays: Ensure L4 GPU quota in the region and that Autopilot supports L4 there.

### Cleanup
```bash
kubectl -n "$NAMESPACE" delete -f gradio.yaml || true
kubectl -n "$NAMESPACE" delete -f vllm-gemma-l4.yaml || true
gcloud container clusters delete "$CLUSTER_NAME" --region "$REGION" --quiet
```

### Notes
- In GKE Autopilot, you must explicitly request GPUs in your Pod (via the `workload.googleapis.com/accelerator` annotation and `nvidia.com/gpu` limit). Autopilot will provision GPU nodes accordingly. See the two Google Cloud docs referenced at the top.
- vLLM exposes Prometheus metrics by default; consider integrating Cloud Monitoring and Google Cloud Managed Service for Prometheus if you need dashboards.


LOGS:
```bash
quan@cloudshell:~ (venerian)$ cat cmds_to_deploy_gemma3.txt 
#     1  gcloud config set project venerian
#     2  gcloud config set billing/quota_project venerian
#     3  export PROJECT_ID=$(gcloud config get project)
#     4  export REGION=us-central1
#     5  export CLUSTER_NAME=venera-llms
#     6  export HF_TOKEN=
#     7  echo $CLUSTER_NAME
#     8  echo $PROJECT_ID
#     9  echo $CONTROL_PLANE_LOCATION
#    10  export CONTROL_PLANE_LOCATION=us-central1
#    11  echo $CONTROL_PLANE_LOCATION
#    12  clear
#    13  export REGION=us-central1
#    14  echo ${REGION}
#    15  echo $REGION
#    16  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --location=$CONTROL_PLANE_LOCATION     --release-channel=rapid
#    17  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#    18  kubectl create secret generic hf-secret     --from-literal=hf_api_token=$HF_TOKEN     --dry-run=client -o yaml | kubectl apply -f -
#    19  kubectl get nodes -o wide
#    20  cat secret/hf-secret
#    21  pwd
#    22  clear
#    23  echo $REGION
#    24  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#    25  ls
#    26  pwd
#    27  mkdir mistral-7b
#    28  cd mistral-7b/
#    29  touch vllm-deployment-mistral-7b-gke.yaml
#    30  nano vllm-deployment-mistral-7b-gke.yaml 
#    31  cat vllm-deployment-mistral-7b-gke.yaml 
#    32  clear
#    33  ls
#    34  clear
#    35  touch vllm-pvc-gke.yaml
#    36  kubectl get storageclass
#    37  nano vllm-pvc-gke.yaml 
#    38  cat vllm-pvc-gke.yaml 
#    39  clear
#    40  kubectl apply -f kubernetes/vllm-pvc-gke.yaml
#    41  ls
#    42  kubectl apply -f vllm-pvc-gke.yaml
#    43  touch vllm-service-internal-gke.yaml
#    44  nano vllm-service-internal-gke.yaml 
#    45  cat vllm-service-internal-gke.yaml 
#    46  clear
#    47  kubectl get pvc
#    48  kubectl describe pvc vllm-models
#    49  clear
#    50  ls
#    51  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#    52  kubectl delete -f vllm-pvc-gke.yaml 
#    53  rm vllm-deployment-mistral-7b-gke.yaml vllm-pvc-gke.yaml 
#    54  touch vllm-deployment-mistral-7b-gke.yaml
#    55  touch vllm-pvc-gke.yaml
#    56  nano vllm-deployment-mistral-7b-gke.yaml 
#    57  cat vllm-deployment-mistral-7b-gke.yaml 
#    58  clear
#    59  nano vllm-pvc-gke.yaml 
#    60  cat vllm-pvc-gke.yaml 
#    61  clear
#    62  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#    63  gcloud container clusters get-credentials venera-llms --region us-central1 --project venerian
#    64  clear
#    65  export PROJECT_ID=$(gcloud config get project)
#    66  export REGION=us-central1
#    67  export CONTROL_PLANE_LOCATION=us-central1
#    68  export CLUSTER_NAME=venera-llms
#    69  export HF_TOKEN=
#    70  ls
#    71  cd mistral-7b/
#    72  clear
#    73  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#    74  cat vllm-pvc-gke.yaml 
#    75  clear
#    76  cat vllm-deployment-mistral-7b-gke.yaml 
#    77  clear
#    78  kubectl apply -f vllm-pvc-gke.yaml
#    79  kubectl delete pvc vllm-models
#    80  kubectl apply -f vllm-pvc-gke.yaml
#    81  kubectl get pvc
#    82  kubectl describe pvc vllm-models
#    83  clear
#    84  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml
#    85  kubectl get pods -o wide
#    86  clear
#    87  kubectl get pods -o wide
#    88  kubectl get pvc -w
#    89  kubectl get pods -w
#    90  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#    91  clear
#    92  kubectl get pods -w
#    93  clear
#    94  rm vllm-deployment-mistral-7b-gke.yaml 
#    95  touch vllm-deployment-mistral-7b-gke.yaml
#    96  nano vllm-deployment-mistral-7b-gke.yaml 
#    97  cat vllm-deployment-mistral-7b-gke.yaml 
#    98  clear
#    99  kubectl describe pvc vllm-models
#   100  kubectl get pvc
#   101  clear
#   102  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   103  kubectl get pods -w
#   104  kubectl describe pod vllm-server-796b64cc9c-7gj72 | sed -n '/Events/,$p'
#   105  kubectl logs vllm-server-796b64cc9c-7gj72 -c vllm --previous | tail -n 80
#   106  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   107  clear
#   108  ls
#   109  rm vllm-
#   110  rm vllm-deployment-mistral-7b-gke.yaml 
#   111  touch vllm-deployment-mistral-7b-gke.yaml
#   112  nano vllm-deployment-mistral-7b-gke.yaml 
#   113  kubectl delete -f vllm-pvc-gke.yaml 
#   114  clear
#   115  kubectl get pods
#   116  kubectl get svc
#   117  clear
#   118  kubectl apply -f vllm-pvc-gke.yaml
#   119  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml
#   120  export PROJECT_ID=$(gcloud config get project)
#   121  export REGION=us-central1
#   122  export CONTROL_PLANE_LOCATION=us-central1
#   123  export CLUSTER_NAME=venera-llms
#   124  export HF_TOKEN=
#   125  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#   126  kubectl logs -f deploy/vllm-server -c vllm
#   127  kubectl get pods -w
#   128  clear
#   129  kubectl get pods -w
#   130  kubectl get pvc
#   131  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   132  touch vllm-llama4-maverick-17b-128e.yaml
#   133  nano vllm-llama4-maverick-17b-128e.yaml 
#   134  kubectl apply -f vllm-llama4-maverick-17b-128e.yaml
#   135  nano vllm-llama4-maverick-17b-128e.yaml 
#   136  kubectl apply -f vllm-llama4-maverick-17b-128e.yaml
#   137  kubectl get pods -w
#   138  kubectl delete -f vllm-llama4-maverick-17b-128e.yaml 
#   139  kubectl get pvc
#   140  clear
#   141  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   142  kubectl get pvc
#   143  clear
#   144  kubectl get pods -w
#   145  kubectl get pvc
#   146  clear
#   147  kubectl get pvc
#   148  kubectl get pods -w
#   149  POD=$(kubectl get pod -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}')
#   150  kubectl exec -it "$POD" -c vllm -- nvidia-smi || true
#   151  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   152  kubectl delete -f vllm-pvc-gke.yaml 
#   153  clear
#   154  cd ..
#   155  ls
#   156  rm -rf mistral-7b/
#   157  gcloud container clusters delete ${CLUSTER_NAME} --zone=${ZONE}
#   158  echo ${ZONE}
#   159  gcloud container clusters delete ${CLUSTER_NAME} --zone=${REGION}
#   160  clear
#   161  gcloud config set project venerian
#   162  gcloud config set billing/quota_project venerian
#   163  export PROJECT_ID=$(gcloud config get project)
#   164  export REGION=us-central1
#   165  export CONTROL_PLANE_LOCATION=us-central1
#   166  export CLUSTER_NAME=venera-llms
#   167  export HF_TOKEN=
#   168  gcloud config set project venerian
#   169  gcloud config set billing/quota_project venerian
#   170  export PROJECT_ID=$(gcloud config get project)
#   171  export REGION=us-central1-a
#   172  export CONTROL_PLANE_LOCATION=us-central1-a
#   173  export CLUSTER_NAME=venera-llms
#   174  export HF_TOKEN=
#   175  clear
#   176  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --location=$CONTROL_PLANE_LOCATION     --release-channel=rapid
#   177  export CONTROL_PLANE_LOCATION=us-central1
#   178  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --location=$CONTROL_PLANE_LOCATION     --release-channel=rapid
#   179  clear
#   180  mkdir mistral
#   181  cd mistral/
#   182  touch hf-token-secret.yaml
#   183  touch vllm-deployment-mistral-7b-gke.yaml
#   184  touch vllm-service-internal-gke.yaml
#   185  ls
#   186  nano hf-token-secret.yaml 
#   187  cat hf
#   188  cat hf-token-secret.yaml 
#   189  clear
#   190  ls
#   191  nano vllm-deployment-mistral-7b-gke.yaml 
#   192  nano vllm-service-internal-gke.yaml 
#   193  cat vllm-deployment-mistral-7b-gke.yaml 
#   194  cat vllm-service-internal-gke.yaml 
#   195  clear
#   196  kubectl apply -f hf-token-secret.yaml 
#   197  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   198  nano vllm-deployment-mistral-7b-gke.yaml 
#   199  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   200  kubectl get pods -w
#   201  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   202  rm vllm-deployment-mistral-7b-gke.yaml 
#   203  touch vllm-deployment-mistral-7b-gke.yaml
#   204  nano vllm-deployment-mistral-7b-gke.yaml 
#   205  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml
#   206  kubectl get pods -w
#   207  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}') && echo $POD
#   208  NS=default
#   209  echo $NS
#   210  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}') && echo $POD
#   211  kubectl describe pod $POD -n $NS
#   212  kubectl logs $POD -n $NS -c vllm --previous --tail=200
#   213  kubectl logs $POD -n $NS -c vllm --tail=200
#   214  kubectl get secret hf-secret -n $NS
#   215  kubectl exec -it $POD -n $NS -c vllm -- nvidia-smi
#   216  NS=default
#   217  kubectl -n $NS set env deployment/vllm-server VLLM_LOGGING_LEVEL=DEBUG
#   218  kubectl -n $NS set env deployment/vllm-server LD_LIBRARY_PATH=/usr/local/nvidia/lib64
#   219  kubectl -n $NS patch deployment vllm-server --type='json'   -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--device=cuda"}]'
#   220  kubectl -n $NS rollout restart deployment/vllm-server
#   221  kubectl -n $NS rollout status deployment/vllm-server
#   222  kubectl -n $NS logs -f deploy/vllm-server -c vllm
#   223  cat vllm-deployment-mistral-7b-gke.yaml 
#   224  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   225  clear
#   226  kubectl get pods
#   227  clear
#   228  gcloud config set project venerian
#   229  gcloud config set billing/quota_project venerian
#   230  export PROJECT_ID=$(gcloud config get project)
#   231  export REGION=us-central1-a
#   232  export CONTROL_PLANE_LOCATION=us-central1
#   233  export CLUSTER_NAME=venera-llms
#   234  export HF_TOKEN=
#   235  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#   236  export REGION=us-central1
#   237  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#   238  clear
#   239  kubectl get pods
#   240  gcloud config set project venerian
#   241  gcloud config set billing/quota_project venerian
#   242  export PROJECT_ID=$(gcloud config get project)
#   243  export REGION=us-central1
#   244  export CONTROL_PLANE_LOCATION=us-central1
#   245  export CLUSTER_NAME=venera-llms
#   246  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#   247  ls
#   248  cd mistral/
#   249  ls
#   250  rm vllm-deployment-mistral-7b-gke.yaml 
#   251  touch vllm-deployment-mistral-7b-gke.yaml
#   252  nano vllm-deployment-mistral-7b-gke.yaml 
#   253  ls
#   254  clear
#   255  kubectl apply -f hf-token-secret.yaml
#   256  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   257  nano vllm-deployment-mistral-7b-gke.yaml 
#   258  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   259  kubectl get pods -w
#   260  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}') && echo $PODOD
#   261  NS=default
#   262  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}') && echo $PODOD
#   263  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}') && echo $POD
#   264  kubectl describe pod $POD -n $NS
#   265  kubectl logs $POD -n $NS -c vllm --tail=200
#   266  $NS set env deployment/vllm-server VLLM_LOGGING_LEVEL=DEBUG
#   267  export VLLM_LOGGING_LEVEL=DEBUG
#   268  echo $VLLM_LOGGING_LEVEL
#   269  POD=$(kubectl get pods -n default -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}')
#   270  NODE=$(kubectl get pod $POD -n default -o jsonpath='{.spec.nodeName}')
#   271  kubectl get node $NODE -L cloud.google.com/gke-accelerator   -o custom-columns=NAME:metadata.name,ACCEL:metadata.labels.cloud\.google\.com/gke-accelerator,GPUs:.status.allocatable.nvidia\.com/gpu
#   272  kubectl exec -it $POD -n default -c vllm -- nvidia-smi
#   273  gcloud compute zones list --filter="region:($REGION)" --format="value(name)" |   xargs -I {} gcloud compute accelerator-types list --zones {}   --format="table(name,zone)" | grep -i nvidia-l4 || true
#   274  clear
#   275  gcloud container node-pools list --cluster=$CLUSTER_NAME --zone=$REGION --project=$PROJECT_ID
#   276  gcloud container clusters describe CLUSTER_NAME     --zone=ZONE     --format="value(nodeConfig.accelerators)"
#   277  gcloud container clusters describe $CLUSTER_NAME     --zone=$REGION     --format="value(nodeConfig.accelerators)"
#   278  kubectl describe nodes
#   279  clear
#   280  gcloud compute accelerator-types list
#   281  clear
#   282  gcloud config set project venerian
#   283  gcloud config set billing/quota_project venerian
#   284  export PROJECT_ID=$(gcloud config get project)
#   285  export REGION=us-central1
#   286  export ZONE=us-central1-a
#   287  export CONTROL_PLANE_LOCATION=us-central1
#   288  export CLUSTER_NAME=venera-test
#   289  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --region=REGION     --release-channel=rapid \
#   290  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --region=REGION     --release-channel=rapid
#   291  gcloud config set project venerian
#   292  gcloud config set billing/quota_project venerian
#   293  export PROJECT_ID=$(gcloud config get project)
#   294  export REGION=us-central1
#   295  export ZONE=us-central1-a
#   296  export CONTROL_PLANE_LOCATION=us-central1
#   297  export CLUSTER_NAME=venera-llms
#   298  export CLUSTER_NAME=venera-test
#   299  gcloud compute accelerator-types list --filter="zone:($REGION-a OR $REGION-b OR $REGION-c)"
#   300  gcloud compute accelerator-types list --filter="name:nvidia-l4 AND zone~$REGION"
#   301  clear
#   302  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --release-channel=rapid
#   303  clear
#   304  ls
#   305  ls ms
#   306  ls m
#   307  ls mistral/
#   308  pwd
#   309  whoami
#   310  gcloud config set project venerian
#   311  gcloud config set billing/quota_project venerian
#   312  export PROJECT_ID=$(gcloud config get project)
#   313  export REGION=us-central1
#   314  export ZONE=us-central1-a
#   315  export CONTROL_PLANE_LOCATION=us-central1
#   316  export CLUSTER_NAME=venera-test
#   317  gcloud container clusters get-credentials $CLUSTER_NAME     --location=$REGION
#   318  clear
#   319  ls
#   320  rm -rf mistral/
#   321  gcloud container clusters get-credentials venera-test --region us-central1 --project venerian
#   322  ls /usr/local/nvidia/lib64
#   323  hf-token-secret.yaml
#   324  touch hf-token-secret.yaml
#   325  touch vllm-deployment-mistral-7b-gke.yaml
#   326  nano hf-token-secret.yaml 
#   327  cat hf-token-secret.yaml 
#   328  nano hf-token-secret.yaml 
#   329  cat hf-token-secret.yaml 
#   330  clear
#   331  nano vllm-deployment-mistral-7b-gke.yaml 
#   332  clear
#   333  cat vllm-deployment-mistral-7b-gke.yaml 
#   334  clear
#   335  export VLLM_LOGGING_LEVEL=DEBUG
#   336  kubectl apply -f hf-token-secret.yaml 
#   337  kubectl apply -f vllm-deployment-mistral-7b-gke.yaml 
#   338  kubectl get pods -w
#   339  NS=default
#   340  kubectl -n $NS patch deployment vllm-server --type='json'   -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--device=cuda"}]'
#   341  POD=$(kubectl get pods -n $NS -l app.kubernetes.io/name=vllm -o jsonpath='{.items[0].metadata.name}')
#   342  kubectl exec -it $POD -n $NS -c vllm -- nvidia-smi
#   343  kubectl get node $NODE -L cloud.google.com/gke-accelerator   -o custom-columns=NAME:metadata.name,ACCEL:metadata.labels.cloud\.google\.com/gke-accelerator,GPUs:.status.allocatable.nvidia\.com/gpu
#   344  clear
#   345  gcloud config set project venerian
#   346  gcloud config set billing/quota_project venerian
#   347  export PROJECT_ID=$(gcloud config get project)
#   348  export REGION=us-central1
#   349  export ZONE=us-central1-a
#   350  export CONTROL_PLANE_LOCATION=us-central1
#   351  export CLUSTER_NAME=venera-L4
#   352  gcloud compute machine-types list --filter="zone:( us-central1-a )"
#   353  kubectl delete -f vllm-deployment-mistral-7b-gke.yaml 
#   354  clear
#   355  CLUSTER_NAME
#   356  $CLUSTER_NAME
#   357  echo $CLUSTER_NAME
#   358  clear
#   359  gcloud container node-pools create l4-pool     --cluster $CLUSTER_NAME --zone $ZONE     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   360  gcloud config set project venerian
#   361  gcloud config set billing/quota_project venerian
#   362  export PROJECT_ID=$(gcloud config get project)
#   363  export REGION=us-central1
#   364  export ZONE=us-central1-a
#   365  export CONTROL_PLANE_LOCATION=us-central1
#   366  export CLUSTER_NAME=venera-L4
#   367  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --zone $ZONE     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   368  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   369  export CLUSTER_NAME=venera_L4
#   370  clear
#   371  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   372  export CLUSTER_NAME=veneraL4
#   373  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   374  clear
#   375  export CLUSTER_NAME=venera_l4
#   376  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
#   377  clear
#   378  export CLUSTER_NAME=veneral4
#   379  gcloud container clusters create $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --machine-type g2-standard-8     --accelerator type=nvidia-l4,count=1     --num-nodes 1 --enable-autoscaling --min-nodes 0 --max-nodes 3
  380  pwd
  381  whoami
  382  gcloud config set project venerian
  383  gcloud config set billing/quota_project venerian
  384  export PROJECT_ID=$(gcloud config get project)
  385  export REGION=us-central1
  386  export ZONE=us-central1-a
  387  export CONTROL_PLANE_LOCATION=us-central1
  388  export CLUSTER_NAME=venera-test
  389  export VLLM_LOGGING_LEVEL=DEBUG
  390  clear
  391  echo $PROJECT_ID
  392  export HF_TOKEN=""
  393  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --region=$REGION     --release-channel=rapid
  394  export CLUSTER_NAME=venera-test1
  395  gcloud container clusters create-auto $CLUSTER_NAME     --project=$PROJECT_ID     --location=$CONTROL_PLANE_LOCATION     --release-channel=rapid
  396  clear
  397  gcloud container clusters get-credentials venera-test1 --region us-central1 --project venerian
  398  clear
  399  kubectl get nodes -o=custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\\.com/gpu
  400  gcloud container clusters describe $CLUSTER_NAME --region $REGION --format='value(autopilot.enabled)'
  401  export NAMESPACE=llm
  402  kubectl get namespaces
  403  kubectl create namespace "$NAMESPACE" || true
  404  kubectl get namespaces
  405  clear
  406  kubectl create secret generic hf-secret     --from-literal=hf_api_token=${HF_TOKEN}     --dry-run=client -o yaml | kubectl apply -f -
  407  echo $HF_TOKEN
  408  kubectl create secret generic hf-secret     --from-literal=hf_api_token="my-hf-token"     --dry-run=client -o yaml | kubectl apply -f -
  409  touch vllm-3-1b-it.yaml
  410  rm vllm-deployment-mistral-7b-gke.yaml 
  411  nano vllm-3-1b-it.yaml 
  412  cat vllm-3-1b-it.yaml 
  413  nano vllm-3-1b-it.yaml 
  414  clear
  415  ls
  416  cat hf-token-secret.yaml 
  417  nano hf-token-secret.yaml 
  418  kubectl -n llm apply -f vllm-3-1b-it.yaml 
  419  kubectl get nodes -o wide
  420  kubectl -n llm get nodes -o wide
  421  kubectl get pods -o wide
  422  kubectl -n llm get pods -o wide
  423  kubectl -n llm get pods -w
  424  cat vllm-3-1b-it.yaml 
  425  kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'
  426  kubectl get nodes -L cloud.google.com/gke-accelerator   -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu
  427  kubectl pods
  428  kubectl -n "$NAMESPACE" logs -f deploy/gemma-server
  429  kubectl -n "$NAMESPACE" delete -f vllm-3-1b-it.yaml 
  430  kubectl -n "$NAMESPACE" delete -f hf-token-secret.yaml 
  431  cat hf-token-secret.yaml 
  432  clear
  433  kubectl -n "$NAMESPACE" apply -f hf-token-secret.yaml 
  434  kubectl -n "$NAMESPACE" apply -f vllm-3-1b-it.yaml 
  435  ls
  436  clear
  437  kubectl get pods -w
  438  kubectl get pods -o wide
  439  kubectl -n llm get pods -o wide
  440  kubectl -n get pods -w
  441  kubectl -n llm get pods -w
  442  kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'
  443  kubectl get nodes -L cloud.google.com/gke-accelerator   -o=custom-columns=NAME:.metadata.name,ACCELERATOR:.metadata.labels.cloud\\.google\\.com/gke-accelerator,GPU:.status.allocatable.nvidia\\.com/gpu
  444  kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'
  445  kubectl -n logs -f -l app=gemma-server
  446  kubectl -n llm logs -f -l app=gemma-server
  447  kubectl -n logs -f -l app=gemma-server
  448  kubectl -n llm logs -f -l app=gemma-server
  449  clear
  450  kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'
  451  kubectl get pods -w
  452  kubectl -n llm get pods -w
  453  kubectl -n llm describe pod -l app=gemma-server | sed -n '/Events/,$p'
  454  kubectl logs -f -l app=gemma-server
  455  kubectl -n llm logs -f -l app=gemma-server
  456  kubectl port-forward service/llm-service 8000:8000
  457  kubectl -n llm port-forward service/llm-service 8000:8000
  458  history > cmds_to_deploy_gemma3.txt
```