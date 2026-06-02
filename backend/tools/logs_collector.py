"""Log collection from pods."""
import subprocess
from typing import Optional

def collect_logs(namespace: str, pod_name: str, container: Optional[str] = None, lines: int = 100) -> dict:
    try:
        base = ["kubectl", "logs", pod_name, "-n", namespace, f"--tail={lines}"]
        if container:
            base += ["-c", container]
        current = subprocess.run(base, capture_output=True, text=True, timeout=30)
        previous = subprocess.run(base + ["--previous"], capture_output=True, text=True, timeout=30)
        return {
            "current": current.stdout[-5000:] if current.returncode == 0 else f"Error: {current.stderr[:500]}",
            "previous": previous.stdout[-5000:] if previous.returncode == 0 else None,
        }
    except Exception as e:
        return {"current": f"Error: {str(e)}", "previous": None}
