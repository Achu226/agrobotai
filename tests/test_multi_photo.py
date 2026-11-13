"""3-photo scan: extra leaves are checked like the first and averaged for the disease decision."""
import numpy as np
from fastapi.testclient import TestClient

import server
from tests.conftest import LAN_PHONE, jpeg_bytes, leaf_image
from tests.test_api_v1 import _install_both, _register


def _post(client, headers, *imgs):
    files = {"file": ("a.jpg", jpeg_bytes(imgs[0]), "image/jpeg")}
    files |= {f"file{n}": (f"{n}.jpg", jpeg_bytes(img), "image/jpeg") for n, img in enumerate(imgs[1:], start=2)}
    return client.post("/api/v1/analyze", headers=headers, files=files, data={"include_advice": "false"})


def test_three_photos_make_one_scan():
    _install_both()
    phone = TestClient(server.app, client=LAN_PHONE)
    me, _ = _register(phone, username="three_photos")
    res = _post(phone, me, leaf_image(1), leaf_image(2), leaf_image(3))
    assert res.status_code == 200
    disease = res.json()["scan"]["result"]["disease"]
    assert disease["photos"] == 3 and disease["state"] == "disease_detected"
    assert len(phone.get("/api/v1/scans", headers=me).json()["scans"]) == 1
    single = _post(phone, me, leaf_image(4)).json()["scan"]["result"]["disease"]
    assert "photos" not in single                                   # one photo: unchanged response


def test_bad_extra_photo_is_refused_with_its_number():
    _install_both()
    phone = TestClient(server.app, client=LAN_PHONE)
    me, _ = _register(phone, username="bad_second")
    res = _post(phone, me, leaf_image(1), np.full((256, 256, 3), 128, np.uint8))
    assert res.status_code == 422 and "Photo 2" in res.text
    assert phone.get("/api/v1/scans", headers=me).json()["scans"] == []
