import numpy as np

from src.ndre_cri_analyzer import analyze_ndre_cri, calculate_cri_proxy


def test_green_leaf_returns_ndre_and_cri():
    image = np.zeros((80, 80, 3), dtype=np.uint8)
    image[:, :] = (20, 180, 20)
    result = analyze_ndre_cri(image)
    assert result["ok"] is True
    assert result["ndre"]["ok"] is True
    assert result["cri"]["ok"] is True
    assert 0.0 <= result["ndre"]["value"] <= 1.0
    assert 0.0 <= result["cri"]["value"] <= 1.0
    assert result["ndre"]["score"] is not None
    assert result["cri"]["score"] is not None


def test_cri1_formula_matches_source():
    r = np.array([[0.4]], dtype=np.float32)
    g = np.array([[0.6]], dtype=np.float32)
    b = np.array([[0.2]], dtype=np.float32)
    mask = np.array([[True]])
    cri = calculate_cri_proxy(r, g, b, mask, variant="CRI1")
    expected = (1.0 / (0.2 + 1e-8)) - (1.0 / (0.6 + 1e-8))
    assert abs(float(cri[0, 0]) - expected) < 1e-5


def test_empty_image_fails_gracefully():
    result = analyze_ndre_cri(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result["ok"] is False
    assert result["ndre"]["ok"] is False
    assert result["cri"]["ok"] is False
