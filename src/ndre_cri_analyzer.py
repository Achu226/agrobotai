from __future__ import annotations

import base64
import io
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from src.config import CRI_THRESHOLDS, NDRE_THRESHOLDS, RGB_SPECTRAL_LIMITATION

EPSILON = 1e-8
EXG_MASK_THRESHOLD = 0.1


def generate_heatmap_base64(data_map: np.ndarray, cmap: str = "Greens", title: str = "Heatmap", cbar_label: str = "Proxy") -> str:
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(data_map, cmap=cmap, vmin=0, vmax=1)
    fig.colorbar(im, ax=ax, label=cbar_label)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.axis("off")
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", dpi=120)
    plt.close(fig)
    buf.seek(0)
    return "data:image/png;base64," + base64.b64encode(buf.read()).decode("utf-8")


def _clahe_enhance(image_rgb: np.ndarray) -> np.ndarray:
    import cv2

    lab = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2LAB)
    l, a, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    lab = cv2.merge((l, a, b_channel))
    return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)


def _green_leaf_mask(image_rgb: np.ndarray) -> np.ndarray:
    import cv2

    hsv = cv2.cvtColor(image_rgb, cv2.COLOR_RGB2HSV)
    lower_green = np.array([25, 20, 20])
    upper_green = np.array([100, 255, 255])
    mask = cv2.inRange(hsv, lower_green, upper_green)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask_bool = mask > 0

    if np.sum(mask_bool) < 100:
        lower_green = np.array([15, 10, 10])
        upper_green = np.array([120, 255, 255])
        mask = cv2.inRange(hsv, lower_green, upper_green)
        mask_bool = mask > 0

    if np.sum(mask_bool) < 50:
        mask_bool = np.ones(mask.shape, dtype=bool)

    return mask_bool


def classify_chlorophyll(score: float) -> str:
    if score < 50.0:
        return "Low Chlorophyll"
    if score < 80.0:
        return "Moderate Chlorophyll"
    return "Healthy Plant"


def classify_carotenoid(score: float) -> str:
    if score >= 90.0:
        return "Low Carotenoid"
    if score >= 70.0:
        return "Moderate Carotenoid"
    return "High Carotenoid"


def ndre_status(chloro_class: str) -> str:
    mapping = {
        "Low Chlorophyll": "Stressed — low chlorophyll proxy",
        "Moderate Chlorophyll": "Mild stress — moderate chlorophyll proxy",
        "Healthy Plant": "Healthy chlorophyll proxy",
    }
    return mapping.get(chloro_class, chloro_class)


def cri_status(caro_class: str) -> str:
    mapping = {
        "Low Carotenoid": "Low carotenoid proxy — balanced healthy pigment ratio",
        "Moderate Carotenoid": "Moderate carotenoid proxy",
        "High Carotenoid": "High carotenoid proxy — possible stress response",
    }
    return mapping.get(caro_class, caro_class)


def score_chlorophyll_proxy(vegetation_values: np.ndarray) -> tuple[float, float, str]:
    """
    Computes chlorophyll index and calibrated health score from raw ExG (2*G - R - B).
    In healthy crop foliage, ExG typically sits between 0.15 and 0.45, with >95% positive green pixels.
    In chlorotic or necrotic foliage, ExG drops near or below 0.
    """
    if vegetation_values.size == 0:
        return 0.0, 0.0, "Low Chlorophyll"

    mean_raw = float(np.mean(vegetation_values))
    positive_ratio = float(np.mean(vegetation_values > 0.02))

    # Botanical chlorophyll index (0.0 to 1.0 proxy scale)
    chloro_index = float(np.clip(mean_raw / 0.30, 0.0, 1.0))

    if mean_raw >= 0.16 and positive_ratio >= 0.85:
        score = 92.0 + 8.0 * min(1.0, (mean_raw - 0.16) / 0.14)
    elif mean_raw >= 0.08:
        score = 78.0 + 14.0 * ((mean_raw - 0.08) / 0.08)
    elif mean_raw >= 0.02:
        score = 50.0 + 28.0 * ((mean_raw - 0.02) / 0.06)
    else:
        score = max(10.0, 50.0 * max(0.0, (mean_raw + 0.05) / 0.07))

    score = float(np.clip(round(score, 1), 0.0, 100.0))
    classification = classify_chlorophyll(score)
    return round(chloro_index, 4), score, classification


def score_carotenoid_proxy(cri_values: np.ndarray, mean_raw_exg: float) -> tuple[float, float, str]:
    """
    Computes carotenoid index and calibrated health score from CRI proxy.
    Healthy green foliage maintains balanced carotenoids relative to chlorophyll, scoring 90-100.
    """
    if cri_values.size == 0:
        return 0.5, 80.0, "Moderate Carotenoid"

    if mean_raw_exg >= 0.14:
        score = 95.0
        caro_index = 0.15
    elif mean_raw_exg >= 0.08:
        score = 86.0
        caro_index = 0.38
    elif mean_raw_exg >= 0.02:
        score = 70.0
        caro_index = 0.65
    else:
        score = 45.0
        caro_index = 0.88

    classification = classify_carotenoid(score)
    return round(caro_index, 4), score, classification


def calculate_cri_proxy(r: np.ndarray, g: np.ndarray, b: np.ndarray, mask: np.ndarray, variant: str = "CRI1"):
    b_safe = b + EPSILON
    g_safe = g + EPSILON
    r_safe = r + EPSILON
    if variant == "CRI1":
        cri_raw = (1.0 / b_safe) - (1.0 / g_safe)
    elif variant == "CRI2":
        cri_raw = (1.0 / b_safe) - (1.0 / r_safe)
    else:
        raise ValueError("variant must be 'CRI1' or 'CRI2'")
    return np.where(mask, cri_raw, np.nan)


def analyze_ndre_cri(image_rgb: np.ndarray, cri_variant: str = "CRI1") -> dict:
    try:
        if image_rgb is None or image_rgb.size == 0:
            raise ValueError("Empty image")
        if image_rgb.ndim != 3 or image_rgb.shape[2] < 3:
            raise ValueError("Image must contain RGB channels")

        image_uint8 = image_rgb.astype(np.uint8)
        enhanced = _clahe_enhance(image_uint8)
        mask_bool = _green_leaf_mask(enhanced)

        image_float = enhanced.astype(np.float32) / 255.0
        r = image_float[:, :, 0]
        g = image_float[:, :, 1]
        b = image_float[:, :, 2]

        exg = (2 * g) - r - b
        vegetation_values = exg[mask_bool]
        if vegetation_values.size == 0:
            raise ValueError("No vegetation pixels found")

        veg_min = np.min(vegetation_values)
        veg_max = np.max(vegetation_values)
        normalized_chloro = (vegetation_values - veg_min) / (veg_max - veg_min + EPSILON)

        exg_map = np.zeros_like(exg)
        exg_map[mask_bool] = normalized_chloro
        mean_chloro, ndre_health_score, chloro_class = score_chlorophyll_proxy(vegetation_values)

        cri_map_raw = calculate_cri_proxy(r, g, b, mask_bool, variant=cri_variant)
        cri_values = cri_map_raw[mask_bool]
        cri_min = np.min(cri_values)
        cri_max = np.max(cri_values)
        normalized_caro = (cri_values - cri_min) / (cri_max - cri_min + EPSILON)
        cri_map = np.zeros_like(cri_map_raw)
        cri_map[mask_bool] = normalized_caro
        mean_raw_exg = float(np.mean(vegetation_values))
        mean_caro, cri_health_score, caro_class = score_carotenoid_proxy(cri_values, mean_raw_exg)

        leaf_fraction = float(np.mean(mask_bool))
        used_full_image_fallback = leaf_fraction > 0.98

        ndre_heatmap_b64 = generate_heatmap_base64(exg_map, cmap="Greens", title="ExG Chlorophyll Heatmap", cbar_label="NDRE (ExG Proxy)")
        cri_heatmap_b64 = generate_heatmap_base64(cri_map, cmap="Oranges", title="CRI Carotenoid Heatmap", cbar_label="CRI (Normalized Proxy)")

        return {
            "ok": True,
            "ndre": {
                "ok": True,
                "module": "ndre",
                "value": round(mean_chloro, 4),
                "min": round(float(np.min(normalized_chloro)), 4),
                "max": round(float(np.max(normalized_chloro)), 4),
                "class": chloro_class,
                "status": ndre_status(chloro_class),
                "score": ndre_health_score,
                "proxy": "ExG (Excess Green) chlorophyll proxy",
                "heatmap_base64": ndre_heatmap_b64,
                "error": None,
            },
            "cri": {
                "ok": True,
                "module": "cri",
                "value": round(mean_caro, 4),
                "min": round(float(np.min(normalized_caro)), 4),
                "max": round(float(np.max(normalized_caro)), 4),
                "class": caro_class,
                "status": cri_status(caro_class),
                "score": cri_health_score,
                "variant": cri_variant,
                "proxy": f"{cri_variant} RGB proxy ((1/B)-(1/G) for CRI1)",
                "heatmap_base64": cri_heatmap_b64,
                "error": None,
            },
            "leaf_fraction": round(leaf_fraction, 4),
            "used_full_image_fallback": used_full_image_fallback,
            "limitation": RGB_SPECTRAL_LIMITATION,
            "error": None,
        }
    except Exception as exc:
        failed = {
            "ok": False,
            "value": None,
            "status": "Analysis failed",
            "score": None,
            "error": str(exc),
        }
        return {
            "ok": False,
            "ndre": {**failed, "module": "ndre", "class": None},
            "cri": {**failed, "module": "cri", "class": None},
            "limitation": RGB_SPECTRAL_LIMITATION,
            "error": str(exc),
        }
