# ⎈ K8s AI Debugger

An AI-powered Kubernetes troubleshooting agent that automatically investigates cluster failures, identifies root causes using multiple AI models, and provides actionable fix recommendations — across all major failure types.

## What it does

You point it at a namespace, pod, deployment, or job. It collects evidence from your cluster using `kubectl`, sends everything to Claude (or multiple models simultaneously) for analysis, and returns a structured diagnosis with exact commands to fix the problem.

No more manually running `kubectl describe`, `kubectl logs`, `kubectl get events` one by one trying to piece together what went wrong.

---

## Supported failure types

| Category | What it detects |
|---|---|
| `pod_crash` | CrashLoopBackOff, OOMKilled, container exit errors |
| `image_pull` | ImagePullBackOff, ErrImagePull, wrong registry or tag |
| `scheduling` | Pending pods, insufficient CPU/memory, taint/toleration mismatch, node affinity |
| `node_health` | NotReady nodes, disk pressure, memory pressure, PID pressure |
| `storage` | PVC unbound, missing StorageClass, volume mount failures |
| `rbac` | Forbidden events, missing Role/ClusterRole, wrong ServiceAccount |
| `quota` | ResourceQuota exhausted, LimitRange violations |
| `hpa` | HPA can't scale, metrics-server unavailable, at max replicas |
| `job_failure` | Job backoff limit reached, CronJob suspended or repeatedly failing |
| `cert_expiry` | TLS secret expired or expiring within 30 days, cert-manager not ready |
| `networking` | No ready endpoints, service selector mismatch, LoadBalancer pending, ingress issues |
| `rollout` | Deployment progress deadline exceeded, replicas not available |
| `config_error` | Missing ConfigMap/Secret, CreateContainerConfigError |
| `argocd_sync` | ArgoCD app out of sync, sync failed, unhealthy resources in GitOps pipeline |
| `unknown` | Evidence collected but root cause unclear — raw data provided for manual review |

---

## Architecture

```
Kubernetes Cluster
      ↓
Investigation Layer (backend/tools/)
  ├── pod_inspector.py              pod health, crash detection, OOM
  ├── logs_collector.py             current + previous container logs
  ├── events_analyzer.py            warning events sorted by timestamp
  ├── deployment_inspector.py       rollout status, StatefulSets
  ├── network_inspector.py          services, endpoints, ingresses
  ├── node_inspector.py             node conditions, pressure, taints, metrics
  ├── storage_inspector.py          PVCs, StorageClasses
  ├── rbac_inspector.py             roles, bindings, Forbidden events
  ├── resource_quota_inspector.py   quota usage, LimitRanges, HPA
  ├── job_inspector.py              Jobs, CronJobs
  ├── cert_inspector.py             TLS secrets, cert-manager certificates
  └── argocd_inspector.py           ArgoCD app health, sync status, resource tree
      ↓
AI Agent Layer (backend/agents/)
  ├── investigator.py   collects all evidence → single model analysis
  └── ensemble.py       sends to multiple LLMs in parallel → correlates results
      ↓
Persistence (backend/db/database.py)
  └── SQLite — investigation history + user feedback
      ↓
FastAPI Backend (backend/api/routes.py)
  ├── POST /api/v1/investigate         async investigation (returns ID immediately)
  ├── POST /api/v1/investigate/sync    synchronous (waits for result)
  ├── GET  /api/v1/investigation/{id}  poll result
  ├── GET  /api/v1/history             list all past investigations
  ├── POST /api/v1/investigation/{id}/feedback
  ├── GET  /api/v1/namespaces          list cluster namespaces
  └── GET  /api/v1/health
      ↓
Frontend (frontend/index.html)
  └── Dark mode dashboard — history sidebar, tabbed results,
      model comparison view, copy-to-clipboard fix commands
```

---

## Multi-Model Ensemble

One of the unique features of this project is **multi-model correlation** — sending the same evidence to multiple AI models simultaneously and comparing their diagnoses to reduce noise and increase confidence.

```
Same kubectl evidence
        ↓
Claude (Anthropic)  ──┐
OpenRouter model    ──┼──→ run in parallel → correlate → result
Gemini (Google)     ──┘
        ↓
All agree  → HIGH correlation  → confidence +20%
2 agree    → MEDIUM            → confidence +10%
All differ → LOW               → flag for human review
```

### Fully automatic — no toggles needed

The system reads your `.env`, counts how many API keys are present, and decides the mode automatically. You never need to change a config value:

| Keys in `.env` | What happens automatically |
|---|---|
| 1 key | Runs that model only |
| 2 keys | Runs both in parallel — 2-way correlation |
| 3 keys | Full 3-way correlation — highest confidence |

Just add your API keys and the system handles the rest.

### Supported providers

| Provider | Key in `.env` | Default model | Get key |
|---|---|---|---|
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` | [console.anthropic.com](https://console.anthropic.com) — $5 free credits |
| OpenRouter | `OPENROUTER_API_KEY` | `anthropic/claude-3-haiku` | [openrouter.ai](https://openrouter.ai) — free credits |
| Google Gemini | `GEMINI_API_KEY` | `gemini-1.5-flash` | [aistudio.google.com](https://aistudio.google.com) — free tier |

### Example `.env` configurations

```env
# Single model — just Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Two models — automatic 2-way correlation
ANTHROPIC_API_KEY=sk-ant-...
GEMINI_API_KEY=...

# Three models — full ensemble, highest confidence
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
GEMINI_API_KEY=...
```

The dashboard shows a **Model Comparison** tab with:
- Correlation badge — `HIGH` / `MEDIUM` / `LOW` / `SINGLE`
- Category votes — how many models picked each failure type
- Individual model cards with confidence score, root cause, and agreement status
- Human review flag when models strongly disagree

---

## Setup

### Prerequisites
- Python 3.10+
- `kubectl` configured and pointing to your cluster (`kubectl get nodes` should work)
- An API key — Anthropic or OpenRouter (see LLM configuration below)

### 1. Clone and install

```bash
git clone https://github.com/premkumar-palanichamy/k8s-ai-debugger.git
cd k8s-ai-debugger
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` — minimum required:

```env
# Pick one:
ANTHROPIC_API_KEY=sk-ant-...        # direct Anthropic
OPENROUTER_API_KEY=sk-or-...        # or OpenRouter
```

### 3. Run

```bash
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The app automatically finds your kubeconfig from `~/.kube/config` — no need to pass it manually.

Open [http://localhost:8000](http://localhost:8000) for the dashboard.
Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API reference.

---

## Testing with local Minikube

If you want to test the debugger locally without a real cluster, use the included test scenarios that create intentionally broken pods.

### Prerequisites
```bash
# Start minikube
minikube start

# Verify cluster is running
kubectl get nodes
# NAME       STATUS   ROLES           AGE   VERSION
# minikube   Ready    control-plane   11m   v1.31.0
```

### Deploy all broken test scenarios
```bash
# Clone and go into test scenarios folder
cd k8s-test-scenarios
chmod +x scripts/*.sh

# Deploy all 8 broken scenarios
./scripts/deploy-all.sh

# Check their status
./scripts/status.sh
```

Expected pod states after ~30 seconds:
```
test-configerror    → CreateContainerConfigError  (missing ConfigMap)
test-crashloop      → CrashLoopBackOff            (container exits with code 1)
test-failedjob      → Error                       (job hit backoff limit)
test-imagepull      → ImagePullBackOff             (image tag doesn't exist)
test-oom            → CrashLoopBackOff            (OOMKilled — memory too low)
test-pending        → Pending                     (requests 100Gi RAM)
test-storage        → Pending                     (PVC unbound — missing StorageClass)
test-app            → Running                     (but service has wrong selector)
```

### Investigate each scenario

Start the debugger:
```bash
cd k8s-ai-debugger
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open `http://localhost:8000` and investigate:

| What to enter | Expected detection |
|---|---|
| namespace: `default`, scan: `full` | Detects all failures at once |
| pod: `test-crashloop-xxx` | CrashLoopBackOff |
| pod: `test-imagepull-xxx` | ImagePullBackOff |
| pod: `test-oom-xxx` | OOMKilled |
| pod: `test-pending-xxx` | Scheduling failure |
| pod: `test-configerror-xxx` | Missing ConfigMap |
| pod: `test-storage-xxx` | PVC unbound |
| deployment: `test-app` | Service selector mismatch |
| job: `test-failedjob` | Job backoff limit |

### Cleanup
```bash
cd k8s-test-scenarios
./scripts/cleanup.sh
```

---

## Usage

### Dashboard
Use the sidebar to enter a namespace and optional pod/deployment name, choose scan mode, and click **Investigate**. Results appear in tabbed view:
- **Summary** — plain English explanation
- **Signals** — specific evidence that led to the diagnosis
- **Fix Steps** — exact kubectl commands with expected outcomes
- **Prevention** — how to avoid this in future
- **Model Comparison** — ensemble results (if enabled)
- **Raw Evidence** — full JSON from all kubectl tools

### API

```bash
# Investigate a specific pod
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "pod_name": "my-app-xyz-abc"}'

# Full namespace scan
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace": "production", "scan_mode": "full"}'

# Check RBAC for a specific ServiceAccount
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "service_account": "my-sa"}'

# Async — start and poll
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "pod_name": "my-app-xyz"}'
# → {"investigation_id": "abc-123", "status": "running"}

curl http://localhost:8000/api/v1/investigation/abc-123
# → full result when done
```

### Example response

```json
{
  "root_cause": "Container is OOMKilled due to memory limit set too low (128Mi) for actual usage (~300Mi)",
  "failure_category": "pod_crash",
  "confidence": 92,
  "severity": "high",
  "signals": [
    "Container 'app' terminated with reason OOMKilled",
    "Restart count: 14",
    "Memory limit: 128Mi, node reports ~310Mi actual usage"
  ],
  "fix_recommendations": [
    {
      "step": 1,
      "description": "Increase memory limit for the container",
      "command": "kubectl set resources deployment my-app -c app --limits=memory=512Mi",
      "expected_outcome": "Pod restarts without OOMKilled"
    }
  ],
  "prevention": "Set memory requests and limits based on actual observed usage. Use VPA to automate right-sizing.",
  "summary": "The app container is being killed by the kernel because it exceeds its 128Mi memory limit. Increasing the limit to 512Mi should resolve the crashes immediately."
}
```

---

## LLM Configuration

No mode switching needed. Just add the API keys you have — the app figures out the rest.

```env
# Anthropic — direct Claude (get key at console.anthropic.com)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6        # optional, this is the default

# OpenRouter — 100+ models via one key (get key at openrouter.ai)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=anthropic/claude-3-haiku  # optional, this is the default

# Google Gemini — direct Gemini (get key at aistudio.google.com)
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-1.5-flash            # optional, this is the default
```

**Minimum to get started:** one key from any provider above.

---

## ArgoCD Integration

When `ARGOCD_URL` is configured, investigations also include:
- App health and sync status
- Recent deployment history
- Unhealthy resources in the GitOps pipeline
- Sync error messages

```env
ARGOCD_URL=https://your-argocd-server.example.com
ARGOCD_TOKEN=your_argocd_api_token
```

---

## Project structure

```
k8s-ai-debugger/
├── .env.example              environment variable template
├── .gitignore
├── requirements.txt
├── README.md
├── backend/
│   ├── main.py               FastAPI app entry point
│   ├── agents/
│   │   ├── investigator.py   evidence gathering + LLM analysis
│   │   └── ensemble.py       multi-model correlation engine
│   ├── api/
│   │   └── routes.py         HTTP endpoints
│   ├── db/
│   │   └── database.py       SQLite persistence
│   └── tools/                kubectl wrappers (one per concern)
│       ├── pod_inspector.py
│       ├── logs_collector.py
│       ├── events_analyzer.py
│       ├── deployment_inspector.py
│       ├── network_inspector.py
│       ├── node_inspector.py
│       ├── storage_inspector.py
│       ├── rbac_inspector.py
│       ├── resource_quota_inspector.py
│       ├── job_inspector.py
│       ├── cert_inspector.py
│       └── argocd_inspector.py
└── frontend/
    └── index.html            self-contained dark mode dashboard
```

---

## 📝 License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

---

## 🌐 Connect With Me

🏠 [Portfolio](https://ladviksolutions.netlify.app/)<br>
🐙 [GitHub](https://github.com/premkumar-palanichamy)<br>
💼 [LinkedIn](https://linkedin.com/in/premkumarpalanichamy)<br>
▶️ [YouTube](https://www.youtube.com/channel/UCJKEn6HeAxRNirDMBwFfi3w)
