"""PVC / PV / StorageClass inspection."""
import subprocess, json
from typing import Optional

def inspect_pvcs(namespace: str = "default", pod_name: Optional[str] = None) -> dict:
    try:
        cmd = ["kubectl", "get", "pvc", "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "pvcs": []}
        raw = json.loads(result.stdout)
        pvcs = []
        for pvc in raw.get("items", []):
            meta = pvc.get("metadata", {})
            spec = pvc.get("spec", {})
            status = pvc.get("status", {})
            issues = []
            phase = status.get("phase")
            if phase != "Bound":
                issues.append(f"PVC_NOT_BOUND:{phase}:{meta.get('name')}")
            pvcs.append({
                "name": meta.get("name"),
                "namespace": meta.get("namespace"),
                "phase": phase,
                "storage_class": spec.get("storageClassName"),
                "access_modes": spec.get("accessModes", []),
                "requested_storage": spec.get("resources", {}).get("requests", {}).get("storage"),
                "volume_name": spec.get("volumeName"),
                "detected_issues": issues,
            })
        return {"pvcs": pvcs, "unbound_count": sum(1 for p in pvcs if p["phase"] != "Bound")}
    except Exception as e:
        return {"error": str(e), "pvcs": []}

def inspect_storage_classes() -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "storageclass", "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "storage_classes": []}
        raw = json.loads(result.stdout)
        scs = []
        for sc in raw.get("items", []):
            meta = sc.get("metadata", {})
            scs.append({
                "name": meta.get("name"),
                "provisioner": sc.get("provisioner"),
                "reclaim_policy": sc.get("reclaimPolicy"),
                "binding_mode": sc.get("volumeBindingMode"),
                "is_default": meta.get("annotations", {}).get("storageclass.kubernetes.io/is-default-class") == "true",
            })
        return {"storage_classes": scs, "default_class": next((s["name"] for s in scs if s["is_default"]), None)}
    except Exception as e:
        return {"error": str(e), "storage_classes": []}
