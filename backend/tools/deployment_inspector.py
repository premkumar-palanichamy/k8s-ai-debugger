"""Deployment/StatefulSet/DaemonSet inspection."""
import subprocess, json
from typing import Optional

def inspect_deployment(namespace: str = "default", deployment_name: Optional[str] = None) -> dict:
    try:
        kind = "deployment"
        cmd = ["kubectl", "get", kind, deployment_name, "-n", namespace, "-o", "json"] if deployment_name else ["kubectl", "get", "deployments", "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr}
        raw = json.loads(result.stdout)
        items = raw.get("items", [raw]) if "items" in raw else [raw]
        deploys = []
        for d in items:
            meta = d.get("metadata", {})
            status = d.get("status", {})
            spec = d.get("spec", {})
            issues = []
            desired = spec.get("replicas", 1)
            ready = status.get("readyReplicas", 0)
            available = status.get("availableReplicas", 0)
            if ready < desired:
                issues.append(f"REPLICAS_NOT_READY:{ready}/{desired}")
            if available == 0 and desired > 0:
                issues.append("NO_AVAILABLE_REPLICAS")
            for cond in status.get("conditions", []):
                if cond.get("type") == "Progressing" and cond.get("reason") == "ProgressDeadlineExceeded":
                    issues.append(f"ROLLOUT_STALLED:{cond.get('message','')[:100]}")
            deploys.append({
                "name": meta.get("name"),
                "desired": desired,
                "ready": ready,
                "available": available,
                "updated": status.get("updatedReplicas", 0),
                "strategy": spec.get("strategy", {}).get("type"),
                "conditions": status.get("conditions", []),
                "detected_issues": issues,
            })
        return {"deployments": deploys}
    except Exception as e:
        return {"error": str(e)}

def list_deployments(namespace: str = "default") -> dict:
    return inspect_deployment(namespace=namespace)

def inspect_statefulsets(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "statefulsets", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr}
        raw = json.loads(result.stdout)
        sts = []
        for s in raw.get("items", []):
            meta, status, spec = s.get("metadata",{}), s.get("status",{}), s.get("spec",{})
            issues = []
            desired = spec.get("replicas", 1)
            ready = status.get("readyReplicas", 0)
            if ready < desired:
                issues.append(f"STS_REPLICAS_NOT_READY:{ready}/{desired}")
            sts.append({"name": meta.get("name"), "desired": desired, "ready": ready, "current": status.get("currentReplicas",0), "detected_issues": issues})
        return {"statefulsets": sts}
    except Exception as e:
        return {"error": str(e)}
