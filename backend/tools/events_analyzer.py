"""Kubernetes events analysis."""
import subprocess, json
from typing import Optional

def get_events(namespace: str = "default", pod_name: Optional[str] = None, limit: int = 50) -> dict:
    try:
        cmd = ["kubectl", "get", "events", "-n", namespace, "--sort-by=.lastTimestamp", "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "events": []}
        raw = json.loads(result.stdout)
        events = []
        warning_count = 0
        for ev in raw.get("items", [])[-limit:]:
            involved = ev.get("involvedObject", {})
            if pod_name and involved.get("name") != pod_name and not str(involved.get("name","")).startswith(pod_name):
                continue
            ev_type = ev.get("type", "Normal")
            if ev_type == "Warning":
                warning_count += 1
            events.append({
                "type": ev_type,
                "reason": ev.get("reason"),
                "message": ev.get("message", "")[:300],
                "object": f"{involved.get('kind')}/{involved.get('name')}",
                "count": ev.get("count", 1),
                "last_timestamp": ev.get("lastTimestamp"),
            })
        return {"events": events, "warning_count": warning_count, "total": len(events)}
    except Exception as e:
        return {"error": str(e), "events": []}
