"""RBAC / permission inspection - forbidden errors, missing roles, SA misconfigs."""
import subprocess, json
from typing import Optional

def inspect_rbac(namespace: str = "default", service_account: Optional[str] = None) -> dict:
    results = {"service_accounts": [], "roles": [], "role_bindings": [], "detected_issues": []}
    try:
        # Service accounts
        sa_cmd = ["kubectl", "get", "serviceaccounts", "-n", namespace, "-o", "json"]
        sa_result = subprocess.run(sa_cmd, capture_output=True, text=True, timeout=30)
        if sa_result.returncode == 0:
            raw = json.loads(sa_result.stdout)
            results["service_accounts"] = [{"name": i["metadata"]["name"], "secrets": len(i.get("secrets", []))} for i in raw.get("items", [])]

        # Role bindings
        rb_cmd = ["kubectl", "get", "rolebindings", "-n", namespace, "-o", "json"]
        rb_result = subprocess.run(rb_cmd, capture_output=True, text=True, timeout=30)
        if rb_result.returncode == 0:
            raw = json.loads(rb_result.stdout)
            for rb in raw.get("items", []):
                meta = rb.get("metadata", {})
                results["role_bindings"].append({
                    "name": meta.get("name"),
                    "role_ref": rb.get("roleRef", {}),
                    "subjects": rb.get("subjects", []),
                })

        # Check for RBAC-related events (Forbidden)
        ev_cmd = ["kubectl", "get", "events", "-n", namespace, "--field-selector", "reason=Forbidden", "-o", "json"]
        ev_result = subprocess.run(ev_cmd, capture_output=True, text=True, timeout=30)
        if ev_result.returncode == 0:
            raw = json.loads(ev_result.stdout)
            forbidden_events = raw.get("items", [])
            if forbidden_events:
                results["detected_issues"].append(f"RBAC_FORBIDDEN_EVENTS:{len(forbidden_events)} forbidden events detected")
                for ev in forbidden_events[:3]:
                    results["detected_issues"].append(f"FORBIDDEN:{ev.get('message','')[:150]}")

        if service_account:
            # Try auth can-i check
            auth_cmd = ["kubectl", "auth", "can-i", "--list", f"--as=system:serviceaccount:{namespace}:{service_account}", "-n", namespace]
            auth_result = subprocess.run(auth_cmd, capture_output=True, text=True, timeout=30)
            if auth_result.returncode == 0:
                results["sa_permissions"] = auth_result.stdout[:2000]

    except Exception as e:
        results["error"] = str(e)
    return results

def check_cluster_rbac() -> dict:
    """Check cluster-level role bindings."""
    try:
        result = subprocess.run(["kubectl", "get", "clusterrolebindings", "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr}
        raw = json.loads(result.stdout)
        crbs = []
        for crb in raw.get("items", []):
            meta = crb.get("metadata", {})
            crbs.append({"name": meta.get("name"), "role_ref": crb.get("roleRef", {}), "subject_count": len(crb.get("subjects", []))})
        return {"cluster_role_bindings": crbs[:20]}  # limit output
    except Exception as e:
        return {"error": str(e)}
