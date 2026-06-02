"""k8s-ai-debugger — FastAPI application entry point."""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path

from backend.api.routes import router
from backend.db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s — %(message)s")
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
    logger.info("k8s-ai-debugger started — DB initialized")

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
