"""Job and CronJob failure inspection."""
import subprocess, json
from typing import Optional

def inspect_jobs(namespace: str = "default", job_name: Optional[str] = None) -> dict:
    try:
        cmd = ["kubectl", "get", "jobs", "-n", namespace, "-o", "json"]
        if job_name:
            cmd = ["kubectl", "get", "job", job_name, "-n", namespace, "-o", "json"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "jobs": []}
        raw = json.loads(result.stdout)
        items = raw.get("items", [raw]) if "items" in raw else [raw]
        jobs = []
        issues = []
        for job in items:
            meta = job.get("metadata", {})
            status = job.get("status", {})
            spec = job.get("spec", {})
            conditions = status.get("conditions", [])
            job_issues = []
            for cond in conditions:
                if cond.get("type") == "Failed" and cond.get("status") == "True":
                    job_issues.append(f"JOB_FAILED:{cond.get('reason')}:{cond.get('message','')[:120]}")
                    issues.append(f"JOB_FAILED:{meta.get('name')}")
            failed = status.get("failed", 0)
            backoff_limit = spec.get("backoffLimit", 6)
            if failed > 0:
                job_issues.append(f"FAILED_ATTEMPTS:{failed}/{backoff_limit}")
                if failed >= backoff_limit:
                    job_issues.append("BACKOFF_LIMIT_REACHED")
                    issues.append(f"JOB_BACKOFF_LIMIT:{meta.get('name')}")
            jobs.append({
                "name": meta.get("name"),
                "namespace": meta.get("namespace"),
                "active": status.get("active", 0),
                "succeeded": status.get("succeeded", 0),
                "failed": failed,
                "start_time": status.get("startTime"),
                "completion_time": status.get("completionTime"),
                "conditions": conditions,
                "detected_issues": job_issues,
            })
        return {"jobs": jobs, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e), "jobs": []}

def inspect_cronjobs(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(["kubectl", "get", "cronjobs", "-n", namespace, "-o", "json"], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {"error": result.stderr, "cronjobs": []}
        raw = json.loads(result.stdout)
        cronjobs = []
        issues = []
        for cj in raw.get("items", []):
            meta = cj.get("metadata", {})
            spec = cj.get("spec", {})
            status = cj.get("status", {})
            cj_issues = []
            if spec.get("suspend"):
                cj_issues.append("CRONJOB_SUSPENDED")
            last_schedule = status.get("lastScheduleTime")
            failed_jobs = status.get("active", [])
            cronjobs.append({
                "name": meta.get("name"),
                "schedule": spec.get("schedule"),
                "suspended": spec.get("suspend", False),
                "last_schedule_time": last_schedule,
                "active_jobs": len(failed_jobs),
                "failed_jobs_history_limit": spec.get("failedJobsHistoryLimit", 1),
                "detected_issues": cj_issues,
            })
        return {"cronjobs": cronjobs, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e), "cronjobs": []}
