"""Resource quota, LimitRange, and HPA inspection."""
import subprocess, json

def inspect_resource_quotas(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "resourcequota", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "quotas": []}
        raw = json.loads(result.stdout)
        quotas = []
        issues = []
        for rq in raw.get("items", []):
            meta = rq.get("metadata", {})
            status = rq.get("status", {})
            hard = status.get("hard", {})
            used = status.get("used", {})
            quota_info = {"name": meta.get("name"), "hard": hard, "used": used, "near_limit": []}
            for resource, limit in hard.items():
                current = used.get(resource)
                if current:
                    try:
                        pct = _parse_resource_pct(current, limit)
                        if pct >= 80:
                            quota_info["near_limit"].append(f"{resource}: {current}/{limit} ({pct:.0f}%)")
                            if pct >= 95:
                                issues.append(f"QUOTA_NEARLY_EXHAUSTED:{meta['name']}:{resource}={current}/{limit}")
                    except Exception:
                        pass
            quotas.append(quota_info)
        return {"quotas": quotas, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e), "quotas": []}

def inspect_limit_ranges(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "limitrange", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "limit_ranges": []}
        raw = json.loads(result.stdout)
        ranges = []
        for lr in raw.get("items", []):
            meta = lr.get("metadata", {})
            ranges.append({"name": meta.get("name"), "limits": lr.get("spec", {}).get("limits", [])})
        return {"limit_ranges": ranges}
    except Exception as e:
        return {"error": str(e), "limit_ranges": []}

def inspect_hpa(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "hpa", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "hpas": []}
        raw = json.loads(result.stdout)
        hpas = []
        issues = []
        for hpa in raw.get("items", []):
            meta = hpa.get("metadata", {})
            status = hpa.get("status", {})
            spec = hpa.get("spec", {})
            conditions = status.get("conditions", [])
            hpa_issues = []
            for cond in conditions:
                if cond.get("status") == "False":
                    hpa_issues.append(f"HPA_CONDITION_FALSE:{cond.get('type')}:{cond.get('message','')[:100]}")
                    issues.append(f"HPA_ISSUE:{meta.get('name')}:{cond.get('reason')}")
            current = status.get("currentReplicas", 0)
            desired = status.get("desiredReplicas", 0)
            max_r = spec.get("maxReplicas", 0)
            if current == max_r:
                hpa_issues.append(f"HPA_AT_MAX_REPLICAS:{current}/{max_r}")
                issues.append(f"HPA_MAXED_OUT:{meta.get('name')}")
            hpas.append({
                "name": meta.get("name"),
                "target": spec.get("scaleTargetRef", {}),
                "min_replicas": spec.get("minReplicas"),
                "max_replicas": max_r,
                "current_replicas": current,
                "desired_replicas": desired,
                "conditions": conditions,
                "detected_issues": hpa_issues,
            })
        return {"hpas": hpas, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e), "hpas": []}

def _parse_resource_pct(current: str, limit: str) -> float:
    def parse_val(v):
        v = v.strip()
        if v.endswith("m"):
            return int(v[:-1])
        if v.endswith("Ki"):
            return int(v[:-2]) * 1024
        if v.endswith("Mi"):
            return int(v[:-2]) * 1024 * 1024
        if v.endswith("Gi"):
            return int(v[:-2]) * 1024 * 1024 * 1024
        return int(v)
    return (parse_val(current) / parse_val(limit)) * 100
