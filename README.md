# ⎈ K8s AI Debugger

An AI-powered Kubernetes troubleshooting agent that automatically investigates cluster failures, identifies root causes using Claude, and provides actionable fix recommendations — across all major failure types.

## What it does

You point it at a namespace, pod, deployment, or job. It collects evidence from your cluster using `kubectl`, sends everything to Claude for analysis, and returns a structured diagnosis with exact commands to fix the problem.

No more manually running `kubectl describe`, `kubectl logs`, `kubectl get events` one by one trying to piece together what went wrong.

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
  └── argocd_inspector.py          ArgoCD app health, sync status, resource tree
      ↓
AI Agent (backend/agents/investigator.py)
  └── collects all evidence → Claude API → structured JSON result
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
  └── Dark mode dashboard — history sidebar, tabbed results, copy-to-clipboard fixes
```

## Setup

### Prerequisites
- Python 3.10+
- `kubectl` configured and pointing to your cluster (`kubectl get nodes` should work)
- An Anthropic API key — get one at [console.anthropic.com](https://console.anthropic.com)

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

Edit `.env` and set your API key:

```env
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open [http://localhost:8000](http://localhost:8000) for the dashboard.
Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API reference.

## Usage examples

### Dashboard
Use the sidebar to enter a namespace and optional pod/deployment name, choose scan mode, and click **Investigate**.

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

# Check RBAC issues for a specific ServiceAccount
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "service_account": "my-sa"}'

# Async — start and poll
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{"namespace": "default", "pod_name": "my-app-xyz"}'
# → returns {"investigation_id": "abc-123", "status": "running"}

curl http://localhost:8000/api/v1/investigation/abc-123
# → returns full result when done
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
  "prevention": "Set memory requests and limits based on actual observed usage. Use VPA (Vertical Pod Autoscaler) to automate right-sizing.",
  "summary": "The app container is being killed by the kernel because it exceeds its 128Mi memory limit. Increasing the limit to 512Mi should resolve the crashes immediately."
}
```

## LLM configuration

The agent uses Claude directly via the Anthropic SDK by default. If `ANTHROPIC_API_KEY` is set, it uses that. It also supports OpenRouter as a fallback (useful for free tier or trying different models).

```env
# Direct Anthropic (default, recommended)
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-sonnet-4-6

# OpenRouter fallback
OPENROUTER_API_KEY=...
OPENROUTER_MODEL=anthropic/claude-3-haiku
```

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
│   │   └── investigator.py   evidence gathering + LLM analysis
│   ├── api/
│   │   └── routes.py         HTTP endpoints
│   ├── db/
│   │   └── database.py       SQLite persistence
│   └── tools/                kubectl wrappers (one per concern)
└── frontend/
    └── index.html            self-contained dashboard
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
