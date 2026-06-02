"""Node inspection - NotReady, disk/memory/PID pressure, taints, capacity issues."""
import subprocess, json

def inspect_nodes() -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "nodes", "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "nodes": []}
        raw = json.loads(result.stdout)
        nodes = []
        for node in raw.get("items", []):
            meta = node.get("metadata", {})
            spec = node.get("spec", {})
            status = node.get("status", {})
            conditions = status.get("conditions", [])
            allocatable = status.get("allocatable", {})
            capacity = status.get("capacity", {})
            issues = []
            for cond in conditions:
                t, s = cond.get("type"), cond.get("status")
                if t == "Ready" and s != "True":
                    issues.append(f"NODE_NOT_READY:{cond.get('reason')}:{cond.get('message','')[:100]}")
                if t == "MemoryPressure" and s == "True":
                    issues.append("MEMORY_PRESSURE")
                if t == "DiskPressure" and s == "True":
                    issues.append("DISK_PRESSURE")
                if t == "PIDPressure" and s == "True":
                    issues.append("PID_PRESSURE")
                if t == "NetworkUnavailable" and s == "True":
                    issues.append("NETWORK_UNAVAILABLE")
            taints = spec.get("taints", [])
            for taint in taints:
                if taint.get("effect") in ("NoSchedule", "NoExecute"):
                    issues.append(f"TAINT:{taint.get('key')}:{taint.get('effect')}")
            nodes.append({
                "name": meta.get("name"),
                "labels": meta.get("labels", {}),
                "conditions": [{"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason")} for c in conditions],
                "allocatable": allocatable,
                "capacity": capacity,
                "taints": taints,
                "unschedulable": spec.get("unschedulable", False),
                "detected_issues": issues,
            })
        return {"nodes": nodes, "count": len(nodes), "not_ready_count": sum(1 for n in nodes if any("NODE_NOT_READY" in i for i in n["detected_issues"]))}
    except Exception as e:
        return {"error": str(e), "nodes": []}

def get_node_metrics() -> dict:
    """Try to get metrics-server data for CPU/memory usage."""
    try:
        result = subprocess.run(["kubectl", "top", "nodes", "--no-headers"], capture_output=True, text=True, timeout=15)
        if result.returncode != 0:
            return {"error": "metrics-server unavailable", "nodes": []}
        metrics = []
        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) >= 5:
                metrics.append({"name": parts[0], "cpu": parts[1], "cpu_pct": parts[2], "memory": parts[3], "memory_pct": parts[4]})
        return {"nodes": metrics}
    except Exception as e:
        return {"error": str(e), "nodes": []}
