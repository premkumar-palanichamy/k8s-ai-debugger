"""Network, service, endpoint, and ingress inspection."""
import subprocess, json
from typing import Optional

def inspect_services(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "services", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "services": []}
        raw = json.loads(result.stdout)
        services = []
        for svc in raw.get("items", []):
            meta, spec, status = svc.get("metadata",{}), svc.get("spec",{}), svc.get("status",{})
            issues = []
            if spec.get("type") == "LoadBalancer":
                ingress = status.get("loadBalancer", {}).get("ingress", [])
                if not ingress:
                    issues.append("LOADBALANCER_PENDING_IP")
            services.append({
                "name": meta.get("name"),
                "type": spec.get("type"),
                "cluster_ip": spec.get("clusterIP"),
                "selector": spec.get("selector", {}),
                "ports": spec.get("ports", []),
                "detected_issues": issues,
            })
        return {"services": services}
    except Exception as e:
        return {"error": str(e), "services": []}

def check_endpoints(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "endpoints", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr}
        raw = json.loads(result.stdout)
        endpoints = []
        issues = []
        for ep in raw.get("items", []):
            meta = ep.get("metadata", {})
            subsets = ep.get("subsets", [])
            ready_count = sum(len(s.get("addresses", [])) for s in subsets)
            notready_count = sum(len(s.get("notReadyAddresses", [])) for s in subsets)
            name = meta.get("name")
            if name == "kubernetes":
                continue
            if ready_count == 0 and name != "kubernetes":
                issues.append(f"NO_READY_ENDPOINTS:{name}")
            endpoints.append({"name": name, "ready": ready_count, "not_ready": notready_count, "detected_issues": [] if ready_count > 0 else [f"NO_ENDPOINTS:{name}"]})
        return {"endpoints": endpoints, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e)}

def inspect_ingresses(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "ingress", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "ingresses": []}
        raw = json.loads(result.stdout)
        ingresses = []
        for ing in raw.get("items", []):
            meta, spec, status = ing.get("metadata",{}), ing.get("spec",{}), ing.get("status",{})
            lb = status.get("loadBalancer", {}).get("ingress", [])
            issues = []
            if not lb:
                issues.append("INGRESS_NO_ADDRESS_ASSIGNED")
            ingresses.append({"name": meta.get("name"), "class": spec.get("ingressClassName"), "rules": spec.get("rules", []), "tls": spec.get("tls", []), "load_balancer": lb, "detected_issues": issues})
        return {"ingresses": ingresses}
    except Exception as e:
        return {"error": str(e), "ingresses": []}
