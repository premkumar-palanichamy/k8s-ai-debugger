"""k8s-ai-debugger — FastAPI application entry point."""
from dotenv import load_dotenv
load_dotenv()  # loads .env file before anything else runs

import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from backend.api.routes import router
from backend.db.database import init_db

# ── Auto-detect kubeconfig ────────────────────────────────────────────
# If KUBECONFIG is not set in .env, try common locations automatically
def _resolve_kubeconfig():
    kubeconfig = os.getenv("KUBECONFIG", "")
    if kubeconfig and Path(kubeconfig).exists():
        return kubeconfig
    # Common locations to check
    candidates = [
        Path.home() / ".kube" / "config",           # standard location
        Path("/etc/kubernetes/admin.conf"),           # server installs
        Path("/var/lib/minikube/kubeconfig"),         # some minikube setups
    ]
    for candidate in candidates:
        if candidate.exists():
            os.environ["KUBECONFIG"] = str(candidate)
            return str(candidate)
    return None

kubeconfig_path = _resolve_kubeconfig()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="K8s AI Debugger",
    description="AI-powered Kubernetes troubleshooting — detects all major failure types using Claude",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

@app.on_event("startup")
async def startup():
    init_db()
    if kubeconfig_path:
        logger.info("k8s-ai-debugger started — kubeconfig: %s", kubeconfig_path)
    else:
        logger.warning("k8s-ai-debugger started — no kubeconfig found! kubectl commands will fail.")
    logger.info("DB initialized")

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
if (frontend_dir / "static").exists():
    app.mount("/static", StaticFiles(directory=frontend_dir / "static"), name="static")

@app.get("/", include_in_schema=False)
async def serve_frontend():
    index = frontend_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"message": "K8s AI Debugger API running. Visit /docs for API reference."}
