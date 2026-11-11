import io

import numpy as np
import pytest
import torch
import torch.nn as nn
from fastapi.testclient import TestClient
from PIL import Image

import server
from src import store
from tests.conftest import LOOPBACK
from src.gradcam_viz import gradcam_for_wrapper


@pytest.fixture()
def client():
    # The dashboard endpoints are laptop-only, so these tests call them as a loopback client
    return TestClient(server.app, client=LOOPBACK)


def _png_bytes(color=(30, 160, 40), size=64):
    buf = io.BytesIO()
    Image.fromarray(np.full((size, size, 3), color, dtype=np.uint8)).save(buf, format="PNG")
    return buf.getvalue()


class _TinyNet(nn.Module):
    def __init__(self, num_classes=3):
        super().__init__()
        self.features = nn.Sequential(nn.Conv2d(3, 8, 3, padding=1), nn.ReLU(), nn.Conv2d(8, 8, 3, stride=4, padding=1))
        self.pool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(8, num_classes)

    def forward(self, x):
        return self.head(self.pool(self.features(x)).flatten(1))


class _Wrapper:
    def __init__(self):
        self.device = torch.device("cpu")
        self.model = _TinyNet()
        self.mean = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
        self.std = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


def test_api_routes_are_not_shadowed_by_frontend_mount(client):
    # Before the fix these were registered after the "/" static mount and returned 405/404
    res = client.post("/api/heatmap", files={"file": ("x.png", b"not an image", "image/png")})
    assert res.status_code == 400
    res = client.post("/api/voice", data={"text": "", "lang": "en"})
    assert res.status_code != 405


def test_health_endpoint_reports_status(client):
    data = client.get("/api/health").json()
    assert data["ok"] is True
    assert set(data["models"]) == {"pest", "disease"}
    assert data["device"] in ("cuda", "cpu")


def test_history_lists_and_deletes_stored_scans(client):
    scan_id = store.insert_scan({
        "source": "web", "crop_reported": "Tomato", "inference_status": "succeeded",
        "disease_label": "Tomato Early Blight", "health_index": 72.5, "severity_pct": 12.3,
        "result_json": {"disease": {"display_name": "Tomato Early Blight"}},
    })
    scans = client.get("/api/history").json()["scans"]
    assert [s["id"] for s in scans] == [scan_id]
    assert scans[0]["severity_pct"] == 12.3 and scans[0]["overall_score"] == 72.5

    assert client.delete(f"/api/history/{scan_id}").json() == {"ok": True}
    assert client.delete(f"/api/history/{scan_id}").status_code == 404
    assert client.get("/api/history").json()["scans"] == []


def test_web_scan_storage_strips_embedded_images():
    stripped = server.store_safe({"ndre": {"score": 70, "heatmap_base64": "data:image/png;base64,AAAA"}, "a": [{"x_base64": "b"}]})
    assert stripped == {"ndre": {"score": 70}, "a": [{}]}


def test_dashboard_analyze_without_models_returns_503(client):
    res = client.post("/api/analyze", files={"file": ("leaf.png", _png_bytes(), "image/png")}, data={"crop": "Tomato"})
    assert res.status_code == 503
    assert client.get("/api/history").json()["scans"] == []


def test_gradcam_for_wrapper_returns_overlay_and_removes_hooks():
    wrapper = _Wrapper()
    image = np.random.default_rng(0).integers(0, 255, (120, 90, 3), dtype=np.uint8)
    cam = gradcam_for_wrapper(wrapper, image)
    assert cam["ok"] is True
    assert cam["overlay"].shape == image.shape
    assert cam["heatmap_base64"].startswith("data:image/jpeg;base64,")
    assert 0 <= cam["class_index"] < 3
    assert not wrapper.model.features[-1]._forward_hooks
