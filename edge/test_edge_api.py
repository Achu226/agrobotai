"""
End-to-end check of a running AGROBOTAI server (Raspberry Pi or laptop) with real photos.

    python edge/test_edge_api.py http://<pi-ip>:8000 photo1.jpg [photo2.jpg ...]

Creates a throw-away farmer account (random name and password, printed nowhere), then checks:
health, model status, invalid-image rejection, /predict/disease, /predict/pest, /analyze (saved scan)
and the PDF report. Exit code 0 = every check passed. Uses only the standard library + requests.
"""
import secrets
import sys
import time

import requests


def main(base: str, photos: list[str]) -> int:
    base = base.rstrip("/")
    failures = 0

    def check(name, ok, detail=""):
        nonlocal failures
        failures += 0 if ok else 1
        print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))

    health = requests.get(f"{base}/health", timeout=10).json()
    models = health.get("models", {})
    check("health", all(m.get("ready") for m in models.values()),
          f"device {health.get('runtime', {}).get('inference_device')}, " + ", ".join(f"{k} ready={v.get('ready')}" for k, v in models.items()))

    user = f"edgetest_{secrets.token_hex(4)}"
    res = requests.post(f"{base}/api/v1/auth/register", json={"username": user, "password": secrets.token_urlsafe(12)}, timeout=10)
    if res.status_code != 201:
        check("register test account", False, res.text[:200])
        return 1
    headers = {"Authorization": f"Bearer {res.json()['token']}"}

    status = requests.get(f"{base}/models/status", headers=headers, timeout=10).json()["models"]
    check("models/status", all(m.get("version") for m in status.values()),
          ", ".join(f"{k} {v.get('version')} ({v.get('backend', 'torch')})" for k, v in status.items()))

    bad = requests.post(f"{base}/api/v1/predict/disease", headers=headers,
                        files={"file": ("leaf.jpg", b"this is not an image", "image/jpeg")}, timeout=30)
    check("invalid image rejected", 400 <= bad.status_code < 500, f"HTTP {bad.status_code}")

    for path in photos:
        with open(path, "rb") as f:
            data = f.read()
        name = path.replace("\\", "/").split("/")[-1]
        for kind in ("disease", "pest"):
            t = time.perf_counter()
            r = requests.post(f"{base}/api/v1/predict/{kind}", headers=headers, files={"file": (name, data, "image/jpeg")}, timeout=120)
            body = r.json()
            check(f"predict/{kind} {name}", r.status_code == 200 and "state" in body,
                  f"{body.get('state')} {body.get('display_name', '')} {body.get('calibrated_confidence', '')}% in {time.perf_counter() - t:.1f}s")
        t = time.perf_counter()
        r = requests.post(f"{base}/api/v1/analyze", headers=headers, files={"file": (name, data, "image/jpeg")},
                          data={"include_advice": "false", "client_request_id": secrets.token_hex(8)}, timeout=180)
        scan = r.json().get("scan", {}) if r.ok else {}
        result = scan.get("result", {})
        check(f"analyze {name}", r.status_code in (200, 201) and scan.get("id"),
              f"scan #{scan.get('id')}: {result.get('summary', {}).get('state')} | disease {result.get('disease', {}).get('display_name')} "
              f"| pest {result.get('pest', {}).get('state')} | {time.perf_counter() - t:.1f}s" if scan else r.text[:200])
        if scan.get("id"):
            pdf = requests.get(f"{base}/api/v1/scans/{scan['id']}/report.pdf", headers=headers, timeout=60)
            check(f"PDF report scan #{scan['id']}", pdf.ok and pdf.content[:4] == b"%PDF", f"{len(pdf.content) // 1024} KB")

    print(f"\nTest account '{user}' was created on the server; delete it from the admin page if you like.")
    print("ALL CHECKS PASSED" if failures == 0 else f"{failures} CHECK(S) FAILED")
    return 1 if failures else 0


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], sys.argv[2:]))
