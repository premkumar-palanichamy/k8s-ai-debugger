# K8s AI Debugger

AI-powered Kubernetes troubleshooting with actionable fixes.

It inspects cluster evidence (`kubectl` signals, logs, events, rollout state, storage, RBAC, networking, jobs, certs), then produces a root-cause analysis and recommended commands.

## Why this project

- Detects common Kubernetes failure categories in one flow.
- Gives direct, copy-ready fix commands.
- Supports single-model and multi-model AI correlation automatically.
- Includes local broken manifests for end-to-end testing.

## Screenshots

### Dashboard

![Dashboard Home](docs/images/dashboard-home.png)

### Investigation Running

![Dashboard Investigation](docs/images/dashboard-investigation.png)

### Interactive API Docs

![Swagger API Docs](docs/images/api-docs.png)

## Quick start

```bash
git clone https://github.com/premkumar-palanichamy/k8s-ai-debugger.git
cd k8s-ai-debugger
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
touch .env
```

Set at least one API key in `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
# or OPENROUTER_API_KEY=your_key_here
# or GEMINI_API_KEY=your_key_here
```

Run:

```bash
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:

- Dashboard: http://localhost:8000
- API docs: http://localhost:8000/docs

## Common commands

```bash
# Start app
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Sync investigation
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default","scan_mode":"full"}'

# Async investigation
curl -X POST http://localhost:8000/api/v1/investigate \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default","pod_name":"my-app-pod"}'

# Poll result
curl http://localhost:8000/api/v1/investigation/<investigation_id>
```

## Local k8s test scenarios

```bash
cd k8s
chmod +x scripts/*.sh
./scripts/deploy-all.sh
./scripts/status.sh
```

Cleanup:

```bash
cd k8s
./scripts/cleanup.sh
```

## Failure categories covered

- pod crash / restart failures
- image pull failures
- scheduling / pending pods
- node health pressure states
- storage and PVC binding issues
- RBAC access failures
- quota and limit violations
- HPA scaling issues
- job and cronjob failures
- TLS and certificate expiry paths
- networking and endpoint mismatches
- rollout and deployment progression failures
- config and secret reference errors

## Documentation

- [Quickstart](docs/quickstart.md)
- [Local Kubernetes Testing](docs/testing-local-k8s.md)

## 📝 License

This project is licensed under the terms of the [LICENSE](LICENSE) file.

## 🌐 Connect With Me

🏠 [Portfolio](https://ladviksolutions.netlify.app/)<br>
🐙 [GitHub](https://github.com/premkumar-palanichamy)<br>
💼 [LinkedIn](https://linkedin.com/in/premkumarpalanichamy)<br>
▶️ [YouTube](https://www.youtube.com/channel/UCJKEn6HeAxRNirDMBwFfi3w)
