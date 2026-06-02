"""
ArgoCD integration — inspects application health, sync status,
resource tree, and recent sync history to enrich investigation evidence.
"""
import os
import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)


def _get_argocd_client() -> Optional[httpx.Client]:
    """
    Build an authenticated httpx client for the ArgoCD API.
    Returns None if ArgoCD is not configured.
    """
    url = os.getenv("ARGOCD_URL", "").strip()
    if not url:
        return None

    token = os.getenv("ARGOCD_TOKEN", "").strip()

    # If no token, try username/password login to get one
    if not token:
        username = os.getenv("ARGOCD_USERNAME", "admin")
        password = os.getenv("ARGOCD_PASSWORD", "")
        if not password:
            logger.warning("ArgoCD configured but no token or password provided")
            return None
        try:
            response = httpx.post(
                f"{url}/api/v1/session",
                json={"username": username, "password": password},
                verify=False,
                timeout=10,
            )
            response.raise_for_status()
            token = response.json().get("token", "")
        except Exception as e:
            logger.warning("ArgoCD login failed: %s", e)
            return None

    return httpx.Client(
        base_url=url,
        headers={"Authorization": f"Bearer {token}"},
        verify=False,   # self-signed certs common in ArgoCD
        timeout=15,
    )


def inspect_argocd_apps(namespace: Optional[str] = None) -> dict:
    """
    List all ArgoCD applications, optionally filtered by destination namespace.
    Detects unhealthy or out-of-sync apps.
    """
    client = _get_argocd_client()
    if not client:
        return {"argocd": "not_configured"}

    try:
        response = client.get("/api/v1/applications")
        response.raise_for_status()
        raw = response.json()

        apps = []
        issues = []

        for app in raw.get("items", []):
            meta = app.get("metadata", {})
            spec = app.get("spec", {})
            status = app.get("status", {})

            dest = spec.get("destination", {})
            app_namespace = dest.get("namespace", "")

            # Filter by namespace if requested
            if namespace and app_namespace != namespace:
                continue

            health = status.get("health", {}).get("status", "Unknown")
            sync = status.get("sync", {}).get("status", "Unknown")
            conditions = status.get("conditions", [])

            app_issues = []

            if health not in ("Healthy",):
                app_issues.append(f"APP_UNHEALTHY:{meta.get('name')}:health={health}")
                issues.append(f"ARGOCD_UNHEALTHY:{meta.get('name')}")

            if sync not in ("Synced",):
                app_issues.append(f"APP_OUT_OF_SYNC:{meta.get('name')}:sync={sync}")
                issues.append(f"ARGOCD_OUT_OF_SYNC:{meta.get('name')}")

            for cond in conditions:
                if cond.get("type") in ("SyncError", "ComparisonError", "InvalidSpecError"):
                    app_issues.append(f"ARGOCD_CONDITION:{cond['type']}:{cond.get('message','')[:120]}")

            apps.append({
                "name": meta.get("name"),
                "namespace": meta.get("namespace"),
                "destination_namespace": app_namespace,
                "destination_server": dest.get("server"),
                "source": {
                    "repo": spec.get("source", {}).get("repoURL"),
                    "path": spec.get("source", {}).get("path"),
                    "target_revision": spec.get("source", {}).get("targetRevision"),
                },
                "health_status": health,
                "sync_status": sync,
                "operation_state": status.get("operationState", {}).get("phase"),
                "conditions": conditions,
                "detected_issues": app_issues,
            })

        return {
            "apps": apps,
            "total": len(apps),
            "unhealthy_count": sum(1 for a in apps if a["health_status"] != "Healthy"),
            "out_of_sync_count": sum(1 for a in apps if a["sync_status"] != "Synced"),
            "detected_issues": issues,
        }

    except Exception as e:
        logger.warning("ArgoCD app inspection failed: %s", e)
        return {"argocd_error": str(e), "apps": []}
    finally:
        client.close()


def inspect_argocd_app_detail(app_name: str) -> dict:
    """
    Get detailed info for a specific ArgoCD application —
    resource tree, recent sync history, and operation state.
    """
    client = _get_argocd_client()
    if not client:
        return {"argocd": "not_configured"}

    try:
        # App detail
        response = client.get(f"/api/v1/applications/{app_name}")
        response.raise_for_status()
        app = response.json()

        status = app.get("status", {})
        spec = app.get("spec", {})

        # Sync history (last 5)
        history = status.get("history", [])[-5:]

        # Operation state (last sync result)
        op_state = status.get("operationState", {})
        sync_result = op_state.get("syncResult", {})

        # Resource health summary
        resources = status.get("resources", [])
        unhealthy_resources = [
            {
                "kind": r.get("kind"),
                "name": r.get("name"),
                "namespace": r.get("namespace"),
                "health": r.get("health", {}).get("status"),
                "message": r.get("health", {}).get("message", "")[:120],
            }
            for r in resources
            if r.get("health", {}).get("status") not in ("Healthy", None)
        ]

        return {
            "name": app_name,
            "health_status": status.get("health", {}).get("status"),
            "sync_status": status.get("sync", {}).get("status"),
            "last_sync": {
                "phase": op_state.get("phase"),
                "message": op_state.get("message", "")[:200],
                "started_at": op_state.get("startedAt"),
                "finished_at": op_state.get("finishedAt"),
                "revision": sync_result.get("revision"),
            },
            "source": spec.get("source", {}),
            "sync_history": [
                {
                    "revision": h.get("revision"),
                    "deployed_at": h.get("deployedAt"),
                    "id": h.get("id"),
                }
                for h in history
            ],
            "unhealthy_resources": unhealthy_resources,
            "detected_issues": [
                f"UNHEALTHY_RESOURCE:{r['kind']}/{r['name']}:{r['health']}:{r['message']}"
                for r in unhealthy_resources
            ],
        }

    except Exception as e:
        logger.warning("ArgoCD app detail failed for %s: %s", app_name, e)
        return {"argocd_error": str(e)}
    finally:
        client.close()