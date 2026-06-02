"""Certificate and TLS inspection - expiry, cert-manager, secret-based certs."""
import subprocess, json, base64, ssl, socket
from datetime import datetime, timezone
from typing import Optional

def inspect_tls_secrets(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(
            ["kubectl", "get", "secrets", "-n", namespace, "--field-selector", "type=kubernetes.io/tls", "-o", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"error": result.stderr, "tls_secrets": []}
        raw = json.loads(result.stdout)
        secrets = []
        issues = []
        for secret in raw.get("items", []):
            meta = secret.get("metadata", {})
            data = secret.get("data", {})
            cert_data = data.get("tls.crt", "")
            info = {"name": meta.get("name"), "namespace": meta.get("namespace"), "detected_issues": []}
            if cert_data:
                try:
                    cert_pem = base64.b64decode(cert_data).decode("utf-8")
                    expiry = _parse_cert_expiry(cert_pem)
                    if expiry:
                        info["expiry"] = expiry.isoformat()
                        days_left = (expiry - datetime.now(timezone.utc)).days
                        info["days_until_expiry"] = days_left
                        if days_left < 0:
                            info["detected_issues"].append(f"CERT_EXPIRED:{meta.get('name')}")
                            issues.append(f"CERT_EXPIRED:{meta.get('name')}")
                        elif days_left < 30:
                            info["detected_issues"].append(f"CERT_EXPIRING_SOON:{days_left}d_left")
                            issues.append(f"CERT_EXPIRING_SOON:{meta.get('name')}:{days_left}d")
                except Exception as e:
                    info["detected_issues"].append(f"CERT_PARSE_ERROR:{str(e)}")
            secrets.append(info)
        return {"tls_secrets": secrets, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e), "tls_secrets": []}

def inspect_cert_manager_certs(namespace: str = "default") -> dict:
    try:
        result = subprocess.run(
            ["kubectl", "get", "certificates", "-n", namespace, "-o", "json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            return {"cert_manager": "not_installed_or_no_certs"}
        raw = json.loads(result.stdout)
        certs = []
        issues = []
        for cert in raw.get("items", []):
            meta = cert.get("metadata", {})
            status = cert.get("status", {})
            conditions = status.get("conditions", [])
            cert_issues = []
            for cond in conditions:
                if cond.get("type") == "Ready" and cond.get("status") != "True":
                    cert_issues.append(f"CERT_NOT_READY:{cond.get('reason')}:{cond.get('message','')[:100]}")
                    issues.append(f"CERT_MANAGER_CERT_NOT_READY:{meta.get('name')}")
            expiry = status.get("notAfter")
            if expiry:
                expiry_dt = datetime.fromisoformat(expiry.replace("Z", "+00:00"))
                days_left = (expiry_dt - datetime.now(timezone.utc)).days
                if days_left < 30:
                    cert_issues.append(f"CERT_EXPIRING:{days_left}d_left")
            certs.append({
                "name": meta.get("name"),
                "dns_names": cert.get("spec", {}).get("dnsNames", []),
                "issuer": cert.get("spec", {}).get("issuerRef", {}),
                "expiry": expiry,
                "conditions": conditions,
                "detected_issues": cert_issues,
            })
        return {"cert_manager_certs": certs, "detected_issues": issues}
    except Exception as e:
        return {"error": str(e)}

def _parse_cert_expiry(pem: str) -> Optional[datetime]:
    try:
        import tempfile, os
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(pem)
            tmp = f.name
        result = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-in", tmp], capture_output=True, text=True)
        os.unlink(tmp)
        if result.returncode == 0:
            date_str = result.stdout.strip().replace("notAfter=", "")
            return datetime.strptime(date_str, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return None
