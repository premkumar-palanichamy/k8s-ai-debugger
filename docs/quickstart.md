# Quickstart

This guide gets K8s AI Debugger running in under 5 minutes.

## 1) Prerequisites

- Python 3.10+
- kubectl configured (test with `kubectl get nodes`)
- At least one LLM API key:
  - `ANTHROPIC_API_KEY`
  - `OPENROUTER_API_KEY`
  - `GEMINI_API_KEY`

## 2) Install

```bash
git clone https://github.com/premkumar-palanichamy/k8s-ai-debugger.git
cd k8s-ai-debugger
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 3) Configure environment

```bash
touch .env
```

Set one key minimum in `.env`:

```env
ANTHROPIC_API_KEY=your_key_here
# or
OPENROUTER_API_KEY=your_key_here
# or
GEMINI_API_KEY=your_key_here
```

## 4) Run

```bash
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

Open:
- Dashboard: http://localhost:8000
- API docs: http://localhost:8000/docs

## 5) First investigation

From the UI:
- Namespace: `default`
- Scan Mode: `Targeted` or `Full namespace`
- Click `Investigate`

From the API:

```bash
curl -X POST http://localhost:8000/api/v1/investigate/sync \
  -H "Content-Type: application/json" \
  -d '{"namespace":"default","scan_mode":"full"}'
```

## Notes

- If one model key is configured, single-model analysis runs.
- If multiple keys are configured, multi-model correlation runs automatically.
