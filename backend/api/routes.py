"""FastAPI routes for k8s-ai-debugger."""
import asyncio, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from backend.agents.investigator import investigate
from backend.db.database import (
    save_investigation, update_investigation, mark_investigation_error,
    get_investigation, list_investigations, save_feedback
)

logger = logging.getLogger(__name__)
router = APIRouter()


class InvestigateRequest(BaseModel):
    namespace: str = Field(default="default", description="Kubernetes namespace")
    pod_name: Optional[str] = Field(default=None, description="Specific pod name")
    deployment_name: Optional[str] = Field(default=None, description="Deployment name")
    node_name: Optional[str] = Field(default=None, description="Node name to focus on")
    job_name: Optional[str] = Field(default=None, description="Job or CronJob name")
    service_account: Optional[str] = Field(default=None, description="ServiceAccount to inspect RBAC for")
    scan_mode: str = Field(default="targeted", description="targeted | full cluster scan")


class FeedbackRequest(BaseModel):
    helpful: bool
    comment: Optional[str] = None


async def _run_investigation(inv_id: str, req: InvestigateRequest):
    try:
        result = await asyncio.to_thread(
            investigate,
            namespace=req.namespace,
            pod_name=req.pod_name,
            deployment_name=req.deployment_name,
            node_name=req.node_name,
            job_name=req.job_name,
            service_account=req.service_account,
            scan_mode=req.scan_mode,
        )
        update_investigation(inv_id, result)
        logger.info("Investigation %s completed: category=%s confidence=%s",
                    inv_id, result.get("analysis", {}).get("failure_category"), result.get("analysis", {}).get("confidence"))
    except Exception as e:
        logger.exception("Investigation %s failed", inv_id)
        mark_investigation_error(inv_id, str(e))


@router.post("/investigate", status_code=202)
async def start_investigation(req: InvestigateRequest, background_tasks: BackgroundTasks):
    """Start an async investigation. Returns investigation ID immediately."""
    inv_id = save_investigation(
        namespace=req.namespace,
        pod_name=req.pod_name,
        deployment_name=req.deployment_name,
        node_name=req.node_name,
        job_name=req.job_name,
        scan_mode=req.scan_mode,
    )
    background_tasks.add_task(_run_investigation, inv_id, req)
    return {"investigation_id": inv_id, "status": "running", "message": "Investigation started. Poll /investigation/{id} for results."}


@router.post("/investigate/sync")
async def investigate_sync(req: InvestigateRequest):
    """Synchronous investigation (waits for result). Use for small/targeted scans."""
    inv_id = save_investigation(
        namespace=req.namespace,
        pod_name=req.pod_name,
        deployment_name=req.deployment_name,
        node_name=req.node_name,
        job_name=req.job_name,
        scan_mode=req.scan_mode,
    )
    try:
        result = await asyncio.to_thread(
            investigate,
            namespace=req.namespace,
            pod_name=req.pod_name,
            deployment_name=req.deployment_name,
            node_name=req.node_name,
            job_name=req.job_name,
            service_account=req.service_account,
            scan_mode=req.scan_mode,
        )
        update_investigation(inv_id, result)
        return {"investigation_id": inv_id, "status": "completed", **result}
    except Exception as e:
        mark_investigation_error(inv_id, str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/investigation/{inv_id}")
async def get_investigation_result(inv_id: str):
    inv = get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv


@router.get("/history")
async def get_history(namespace: Optional[str] = None, limit: int = 50):
    return {"investigations": list_investigations(namespace=namespace, limit=min(limit, 200))}


@router.post("/investigation/{inv_id}/feedback")
async def submit_feedback(inv_id: str, req: FeedbackRequest):
    inv = get_investigation(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    fb_id = save_feedback(inv_id, req.helpful, req.comment)
    return {"feedback_id": fb_id, "message": "Thank you for your feedback!"}


@router.get("/health")
async def health():
    return {"status": "ok", "service": "k8s-ai-debugger"}


@router.get("/namespaces")
async def list_namespaces():
    """List available Kubernetes namespaces."""
    import subprocess
    try:
        result = subprocess.run(["kubectl", "get", "namespaces", "-o", "jsonpath={.items[*].metadata.name}"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0:
            ns_list = result.stdout.strip().split()
            return {"namespaces": ns_list}
    except Exception:
        pass
    return {"namespaces": ["default"]}
