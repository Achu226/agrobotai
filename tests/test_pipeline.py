import numpy as np

from src.image_utils import ImageLoadError, load_rgb_array, prepare_model_input
from src.pipeline import analyze_image
from PIL import Image
from io import BytesIO


def _green_image():
    image = np.zeros((120, 120, 3), dtype=np.uint8)
    image[:, :] = (30, 160, 40)
    return image


def test_prepare_model_input_matches_notebook_shape():
    batch = prepare_model_input(_green_image())
    assert batch.shape == (1, 224, 224, 3)
    assert batch.dtype == np.float32
    assert 0.0 <= batch.min() <= batch.max() <= 1.0


def test_load_rgb_array_from_png_bytes():
    image = Image.fromarray(_green_image())
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    array = load_rgb_array(buffer.getvalue())
    assert array.shape[2] == 3


def test_pipeline_without_models_still_runs_spectral_and_health():
    result = analyze_image(_green_image(), crop="Tomato", pest_model=None, disease_model=None, include_advice=False)
    assert result["pest"]["ok"] is False
    assert result["disease"]["ok"] is False
    assert result["ndre"]["ok"] is True
    assert result["cri"]["ok"] is True
    assert result["overall"]["ok"] is True
    assert result["overall"]["overall_score"] is not None
    assert "pest" in result["overall"]["failed_modules"]
    assert "disease" in result["overall"]["failed_modules"]


def test_corrupt_image_raises():
    try:
        load_rgb_array(b"not-an-image")
        assert False, "expected ImageLoadError"
    except ImageLoadError:
        pass


def test_non_plant_image_rejected():
    non_plant_img = np.zeros((120, 120, 3), dtype=np.uint8) + 128
    non_plant_img[:, :, 0] = 220  # red non-plant image
    result = analyze_image(non_plant_img, crop="Tomato", pest_model=None, disease_model=None, include_advice=False)
    assert result["is_valid_plant"] is False
    assert "Invalid image" in result["validation_error"]
