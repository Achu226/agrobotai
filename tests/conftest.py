import logging

import numpy as np
import pytest
import torch
import torch.nn as nn

from src import api_v1, config, inference_service, model_registry, security
from src.config import DISEASE_CLASSES, PEST_CLASSES
from src.disease_detector import PyTorchDiseaseWrapper
from src.pest_detector import PyTorchPestWrapper

LOOPBACK = ("127.0.0.1", 50000)
LAN_PHONE = ("192.168.1.50", 50000)


class FixedLogitNet(nn.Module):
    """Tiny CNN whose output is a fixed logit vector (so tests know the exact prediction).
    It still has a conv `features` block so Grad-CAM can run on it."""

    def __init__(self, logits):
        super().__init__()
        self.features = nn.Sequential(nn.Conv2d(3, 4, 3, padding=1), nn.ReLU())
        self.head = nn.Linear(4, len(logits))
        with torch.no_grad():
            self.head.weight.zero_()
            self.head.bias.copy_(torch.tensor(logits, dtype=torch.float32))

    def forward(self, x):
        return self.head(self.features(x).mean(dim=(2, 3)))


class ExplodingNet(FixedLogitNet):
    def forward(self, x):
        raise RuntimeError("CUDA error: device-side assert triggered")


def logits_for(num_classes: int, index: int | None, strength: float = 12.0):
    logits = [0.0] * num_classes
    if index is not None:
        logits[index] = strength
    return logits


def install_model(name: str, net: nn.Module | None, error: str | None = None):
    classes = DISEASE_CLASSES if name == "disease" else PEST_CLASSES
    if net is None:
        model_registry.set_state(name, {"name": name, "ready": False, "wrapper": None, "num_classes": len(classes),
                                        "error": error or f"Model file models/{name}_model.pt is missing."})
        return
    wrapper_cls = PyTorchDiseaseWrapper if name == "disease" else PyTorchPestWrapper
    wrapper = wrapper_cls(net, device=torch.device("cpu"))
    model_registry.set_state(name, {"name": name, "ready": True, "wrapper": wrapper, "num_classes": len(classes),
                                    "error": None, "version": f"test-{name}-v1", "architecture": "fixed_logit_net",
                                    "temperature": 1.0, "calibrated": True, "classes": list(classes.values()),
                                    "device": "cpu"})


def leaf_image(seed: int = 0, size: int = 256, base=(45, 140, 50)) -> np.ndarray:
    """Green, textured image: passes the foliage check and the sharpness/brightness gates."""
    rng = np.random.default_rng(seed)
    img = np.array(base, dtype=np.float32) + rng.normal(0, 28, (size, size, 3))
    return np.clip(img, 0, 255).astype(np.uint8)


def jpeg_bytes(img: np.ndarray) -> bytes:
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.fromarray(img).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def isolated_server_state(tmp_path, monkeypatch):
    """Every test gets its own database, image folder and model registry."""
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "test.db")
    images = tmp_path / "scan_images"
    monkeypatch.setattr(inference_service, "SCAN_IMAGES_DIR", images)
    monkeypatch.setattr(api_v1, "SCAN_IMAGES_DIR", images)
    monkeypatch.setattr(security, "_logger", logging.getLogger("agrobotai.tests"))
    monkeypatch.setattr(config, "SENSOR_INGEST_TOKEN", "")
    monkeypatch.setattr(config, "ALLOW_FARMER_SIGNUP", True)
    monkeypatch.setattr(model_registry, "_calibration", lambda: {})
    model_registry.reset()
    install_model("disease", None)
    install_model("pest", None)
    yield
    model_registry.reset()
