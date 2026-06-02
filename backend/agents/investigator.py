"""
Main investigation agent — gathers evidence from all tools, analyzes with Claude.
Supports all failure types: pods, nodes, storage, RBAC, quotas, jobs, certs, networking.
"""
import os, json, logging
from typing import Optional
from datetime import datetime, timezone

from backend.tools.pod_inspector import inspect_pods
from backend.tools.logs_collector import collect_logs
from backend.tools.events_analyzer import get_events
from backend.tools.deployment_inspector import inspect_deployment, list_deployments, inspect_statefulsets
from backend.tools.network_inspector import inspect_services, check_endpoints, inspect_ingresses
from backend.tools.node_inspector import inspect_nodes, get_node_metrics
from backend.tools.storage_inspector import inspect_pvcs, inspect_storage_classes
from backend.tools.rbac_inspector import inspect_rbac
from backend.tools.resource_quota_inspector import inspect_resource_quotas, inspect_limit_ranges, inspect_hpa
from backend.tools.job_inspector import inspect_jobs, inspect_cronjobs
from backend.tools.cert_inspector import inspect_tls_secrets, inspect_cert_manager_certs
from backend.tools.argocd_inspector import inspect_argocd_apps, inspect_argocd_app_detail

logger = logging.getLogger(__name__)

# Import ensemble — automatically used when 2+ API keys are configured
from backend.agents.ensemble import analyze_with_ensemble_sync

SYSTEM_PROMPT = """You are an expert Kubernetes Site Reliability Engineer (SRE) with deep expertise in:
- Pod lifecycle, scheduling, and failure patterns
- Node health, resource pressure, and taints
- Persistent storage and volume claims
- RBAC, service accounts, and permission issues
- Resource quotas, LimitRanges, and HPA autoscaling
- Jobs, CronJobs, and batch workloads
- TLS certificates and cert-manager
- Networking, services, endpoints, and ingresses
- GitOps with Argo CD

You are given comprehensive evidence from a Kubernetes cluster. Analyze ALL evidence holistically.

Your tasks:
1. Identify the ROOT CAUSE (not just symptoms)
2. Assign a confidence score (0-100)
3. List specific signals (evidence items) that led to your conclusion
4. Classify the failure category
5. Provide ACTIONABLE fix recommendations with exact commands

FAILURE CATEGORIES:
- pod_crash: CrashLoopBackOff, OOMKilled, container error
- image_pull: ImagePullBackOff, ErrImagePull, wrong tag
- scheduling: Pending, insufficient resources, taints/tolerations, node affinity
- node_health: NotReady, disk/memory/PID pressure, node down
- storage: PVC unbound, StorageClass missing, volume mount failure
- rbac: Forbidden, missing ClusterRole, wrong ServiceAccount
- quota: ResourceQuota exhausted, LimitRange violation
- hpa: HPA can't scale, metrics unavailable, at max replicas
- job_failure: Job backoff limit, CronJob suspended
- cert_expiry: TLS cert expired or expiring
- networking: No endpoints, service selector mismatch, ingress misconfiguration
- rollout: Deployment stuck, progress deadline exceeded
- config_error: ConfigMap/Secret missing, env var misconfiguration
- argocd_sync: ArgoCD app out of sync, sync failed, unhealthy resources in GitOps pipeline
- unknown: Cannot determine root cause

Respond ONLY with valid JSON in this exact format:
{
  "root_cause": "concise description of the root cause",
  "failure_category": "one of the categories above (include argocd_sync if ArgoCD evidence present)",
  "confidence": 85,
  "signals": ["specific evidence item 1", "specific evidence item 2"],
  "affected_resources": ["pod/my-app-xyz", "deployment/my-app"],
  "severity": "critical|high|medium|low",
  "fix_recommendations": [
    {
      "step": 1,
      "description": "what to do",
      "command": "exact kubectl or other command",
      "expected_outcome": "what success looks like"
    }
  ],
  "prevention": "how to prevent this in future",
  "summary": "2-3 sentence plain English explanation for non-experts"
}"""


def gather_evidence(
    namespace: str,
    pod_name: Optional[str] = None,
    deployment_name: Optional[str] = None,
    node_name: Optional[str] = None,
    job_name: Optional[str] = None,
    service_account: Optional[str] = None,
    scan_mode: str = "targeted",  # targeted | full
) -> dict:
    """Collect evidence from all relevant tools based on what's provided."""
    evidence = {"scan_timestamp": datetime.now(timezone.utc).isoformat(), "namespace": namespace}

    # Always collect: pods, events, services
    evidence["pods"] = inspect_pods(namespace=namespace, pod_name=pod_name)
    evidence["events"] = get_events(namespace=namespace, pod_name=pod_name)
    evidence["services"] = inspect_services(namespace=namespace)
    evidence["endpoints"] = check_endpoints(namespace=namespace)

    # Pod logs if specific pod given
    if pod_name:
        evidence["logs"] = collect_logs(namespace=namespace, pod_name=pod_name)

    # Deployment / workload
    if deployment_name:
        evidence["deployment"] = inspect_deployment(namespace=namespace, deployment_name=deployment_name)
    else:
        evidence["deployments"] = list_deployments(namespace=namespace)

    # Full scan or additional targeted data
    if scan_mode == "full" or not pod_name:
        evidence["statefulsets"] = inspect_statefulsets(namespace=namespace)
        evidence["jobs"] = inspect_jobs(namespace=namespace, job_name=job_name)
        evidence["cronjobs"] = inspect_cronjobs(namespace=namespace)
        evidence["hpa"] = inspect_hpa(namespace=namespace)
        evidence["resource_quotas"] = inspect_resource_quotas(namespace=namespace)
        evidence["limit_ranges"] = inspect_limit_ranges(namespace=namespace)
        evidence["ingresses"] = inspect_ingresses(namespace=namespace)

    # Storage
    evidence["pvcs"] = inspect_pvcs(namespace=namespace)
    evidence["storage_classes"] = inspect_storage_classes()

    # RBAC
    evidence["rbac"] = inspect_rbac(namespace=namespace, service_account=service_account)

    # TLS / certs
    evidence["tls_secrets"] = inspect_tls_secrets(namespace=namespace)
    evidence["cert_manager"] = inspect_cert_manager_certs(namespace=namespace)

    # Nodes (always useful context)
    evidence["nodes"] = inspect_nodes()
    evidence["node_metrics"] = get_node_metrics()

    # ArgoCD (optional — only runs if ARGOCD_URL is set in .env)
    evidence["argocd"] = inspect_argocd_apps(namespace=namespace)

    return evidence


def analyze_with_llm(evidence: dict) -> dict:
    """Send evidence to Claude for root cause analysis."""
    evidence_text = json.dumps(evidence, indent=2, default=str)

    # Truncate if too large (keep most recent/relevant)
    if len(evidence_text) > 80000:
        logger.warning("Evidence too large (%d chars), truncating logs", len(evidence_text))
        if "logs" in evidence:
            evidence["logs"]["current"] = evidence["logs"]["current"][-3000:]
            evidence["logs"]["previous"] = evidence["logs"].get("previous", "")[-2000:] if evidence["logs"].get("previous") else None
        evidence_text = json.dumps(evidence, indent=2, default=str)

    user_message = f"""Investigate this Kubernetes cluster evidence and identify the root cause:

<evidence>
{evidence_text}
</evidence>

Respond with valid JSON only. No markdown, no explanation outside the JSON."""

    # Prefer direct Anthropic API
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    if anthropic_key:
        return _call_anthropic(user_message, anthropic_key)
    return _call_openrouter(user_message)


def _call_anthropic(user_message: str, api_key: str) -> dict:
    import anthropic
    model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=model,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )
    return _parse_llm_response(message.content[0].text)


def _call_openrouter(user_message: str) -> dict:
    import httpx
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3-haiku")
    response = httpx.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={"model": model, "messages": [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}], "temperature": 0.1},
        timeout=90,
    )
    response.raise_for_status()
    return _parse_llm_response(response.json()["choices"][0]["message"]["content"])


def _parse_llm_response(content: str) -> dict:
    content = content.strip()
    if content.startswith("```"):
        lines = content.splitlines()
        content = "\n".join(lines[1:-1]) if lines[-1].strip() == "```" else "\n".join(lines[1:])
    if content.startswith("json"):
        content = content[4:].strip()
    return json.loads(content)


def investigate(
    namespace: str,
    pod_name: Optional[str] = None,
    deployment_name: Optional[str] = None,
    node_name: Optional[str] = None,
    job_name: Optional[str] = None,
    service_account: Optional[str] = None,
    scan_mode: str = "targeted",
) -> dict:
    """
    Main entry point: gather evidence, analyze, return structured result.

    Automatically detects how many LLM API keys are in .env:
      1 key configured  → single model analysis
      2+ keys configured → multi-model ensemble with correlation

    No manual configuration needed — just add API keys.
    """
    logger.info(
        "Starting investigation: namespace=%s pod=%s deployment=%s scan_mode=%s",
        namespace, pod_name, deployment_name, scan_mode
    )

    evidence = gather_evidence(
        namespace=namespace,
        pod_name=pod_name,
        deployment_name=deployment_name,
        node_name=node_name,
        job_name=job_name,
        service_account=service_account,
        scan_mode=scan_mode,
    )

    # Automatically detect how many models are configured
    # 1 key → single model, 2+ keys → ensemble (no manual toggle needed)
    from backend.agents.ensemble import get_configured_models
    configured = get_configured_models()

    if len(configured) > 1:
        logger.info("Auto-detected %d API keys — running ensemble analysis", len(configured))
        ensemble_result = analyze_with_ensemble_sync(evidence)
        correlation = ensemble_result.get("correlation", {})
        # Normalize correlation result into standard analysis shape
        analysis = {
            "root_cause": correlation.get("summary", ""),
            "failure_category": correlation.get("agreed_category", "unknown"),
            "confidence": correlation.get("ensemble_confidence", 0),
            "severity": correlation.get("severity", "unknown"),
            "signals": correlation.get("merged_signals", []),
            "affected_resources": correlation.get("affected_resources", []),
            "fix_recommendations": correlation.get("fix_recommendations", []),
            "prevention": correlation.get("prevention", ""),
            "summary": correlation.get("summary", ""),
            "correlation": correlation.get("correlation", ""),
            "recommendation": correlation.get("recommendation", ""),
            "needs_human_review": correlation.get("needs_human_review", False),
        }
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "deployment_name": deployment_name,
            "node_name": node_name,
            "job_name": job_name,
            "scan_mode": scan_mode,
            "mode": "ensemble",
            "models_used": [m["label"] for m in configured],
            "evidence": evidence,
            "analysis": analysis,
            "ensemble": ensemble_result,
        }
    else:
        logger.info("Auto-detected %d API key — running single model analysis",
                    len(configured))
        analysis = analyze_with_llm(evidence)
        return {
            "namespace": namespace,
            "pod_name": pod_name,
            "deployment_name": deployment_name,
            "node_name": node_name,
            "job_name": job_name,
            "scan_mode": scan_mode,
            "mode": "single",
            "models_used": [m["label"] for m in configured] if configured else ["none"],
            "evidence": evidence,
            "analysis": analysis,
        }