"""Pod inspection tool - detects CrashLoopBackOff, OOMKilled, Pending, ImagePullBackOff, probe failures."""
import subprocess, json
from typing import Optional

def inspect_pods(namespace: str = "default", pod_name: Optional[str] = None) -> dict:
    try:
        cmd = ["kubectl", "get", "pods", "-n", namespace, "-o", "json"]
        if pod_name:
            cmd = ["kubectl", "get", "pod", pod_name, "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "pods": []}
        raw = json.loads(result.stdout)
        items = raw.get("items", [raw]) if "items" in raw else [raw]
        pods = []
        for pod in items:
            meta = pod.get("metadata", {})
            spec = pod.get("spec", {})
            status = pod.get("status", {})
            containers = status.get("containerStatuses", []) + status.get("initContainerStatuses", [])
            pod_info = {
                "name": meta.get("name"),
                "namespace": meta.get("namespace"),
                "phase": status.get("phase"),
                "node": spec.get("nodeName"),
                "labels": meta.get("labels", {}),
                "conditions": [{"type": c.get("type"), "status": c.get("status"), "reason": c.get("reason"), "message": c.get("message")} for c in status.get("conditions", [])],
                "containers": [],
                "init_containers": [],
                "detected_issues": [],
            }
            for cs in containers:
                state = cs.get("state", {})
                last_state = cs.get("lastState", {})
                c_info = {
                    "name": cs.get("name"),
                    "ready": cs.get("ready"),
                    "restart_count": cs.get("restartCount", 0),
                    "image": cs.get("image"),
                    "state": state,
                    "last_state": last_state,
                }
                pod_info["containers"].append(c_info)
                # Detect failure patterns
                if cs.get("restartCount", 0) >= 3:
                    pod_info["detected_issues"].append(f"HIGH_RESTART_COUNT:{cs['name']}={cs['restartCount']}")
                terminated = state.get("terminated") or last_state.get("terminated", {})
                if terminated:
                    reason = terminated.get("reason", "")
                    if reason == "OOMKilled":
                        pod_info["detected_issues"].append(f"OOM_KILLED:{cs['name']}")
                    if reason == "Error":
                        pod_info["detected_issues"].append(f"CONTAINER_ERROR:{cs['name']}")
                waiting = state.get("waiting", {})
                if waiting:
                    wr = waiting.get("reason", "")
                    if wr in ("CrashLoopBackOff",):
                        pod_info["detected_issues"].append(f"CRASH_LOOP:{cs['name']}")
                    if wr in ("ImagePullBackOff", "ErrImagePull"):
                        pod_info["detected_issues"].append(f"IMAGE_PULL_FAILURE:{cs['name']}:{waiting.get('message','')}")
                    if wr in ("CreateContainerConfigError",):
                        pod_info["detected_issues"].append(f"CONFIG_ERROR:{cs['name']}")
            # Pod-level conditions
            for cond in pod_info["conditions"]:
                if cond["type"] == "PodScheduled" and cond["status"] == "False":
                    pod_info["detected_issues"].append(f"SCHEDULING_FAILED:{cond.get('reason')}:{cond.get('message','')[:120]}")
                if cond["type"] == "Ready" and cond["status"] == "False" and cond.get("reason") == "ContainersNotReady":
                    pod_info["detected_issues"].append("CONTAINERS_NOT_READY")
            pods.append(pod_info)
        return {"pods": pods, "count": len(pods)}
    except subprocess.TimeoutExpired:
        return {"error": "kubectl timeout", "pods": []}
    except Exception as e:
        return {"error": str(e), "pods": []}
