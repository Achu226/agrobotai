from __future__ import annotations

from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, UnidentifiedImageError

from src.config import IMAGE_SIZE, SUPPORTED_IMAGE_TYPES


class ImageLoadError(ValueError):
    pass


def _open_pil(source) -> Image.Image:
    try:
        if isinstance(source, (str, Path)):
            path = Path(source)
            if path.suffix.lower() not in SUPPORTED_IMAGE_TYPES and path.suffix:
                raise ImageLoadError(f"Unsupported image type: {path.suffix}")
            image = Image.open(path)
        elif hasattr(source, "read"):
            data = source.read()
            if hasattr(source, "seek"):
                try:
                    source.seek(0)
                except Exception:
                    pass
            if not data:
                raise ImageLoadError("Empty image file")
            image = Image.open(BytesIO(data))
        elif isinstance(source, bytes):
            image = Image.open(BytesIO(source))
        elif isinstance(source, np.ndarray):
            array = source
            if array.ndim == 2:
                image = Image.fromarray(array)
            elif array.ndim == 3 and array.shape[2] in (3, 4):
                if array.dtype != np.uint8:
                    array = np.clip(array, 0, 255).astype(np.uint8)
                image = Image.fromarray(array)
            else:
                raise ImageLoadError("NumPy image must be HxW or HxWx3/4")
        elif isinstance(source, Image.Image):
            image = source
        else:
            raise ImageLoadError(f"Unsupported image source: {type(source)}")
        image.load()
        return image
    except ImageLoadError:
        raise
    except UnidentifiedImageError as exc:
        raise ImageLoadError("Invalid or corrupt image") from exc
    except Exception as exc:
        raise ImageLoadError(f"Could not load image: {exc}") from exc


def load_rgb_array(source) -> np.ndarray:
    image = _open_pil(source)
    if image.mode == "RGBA":
        background = Image.new("RGB", image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != "RGB":
        image = image.convert("RGB")
    array = np.asarray(image)
    if array.ndim != 3 or array.shape[2] != 3:
        raise ImageLoadError("Image must have 3 RGB channels")
    if array.size == 0:
        raise ImageLoadError("Image is empty")
    return array.astype(np.uint8)


def resize_rgb(image_rgb: np.ndarray, size: tuple[int, int] = IMAGE_SIZE) -> np.ndarray:
    image = Image.fromarray(image_rgb.astype(np.uint8), mode="RGB")
    image = image.resize(size, Image.BILINEAR)
    return np.asarray(image).astype(np.uint8)


def prepare_model_input(image_rgb: np.ndarray, size: tuple[int, int] = IMAGE_SIZE) -> np.ndarray:
    """Match notebook get_img_array: resize 224x224, scale to 0-1, add batch dim."""
    resized = resize_rgb(image_rgb, size)
    array = resized.astype(np.float32) / 255.0
    return np.expand_dims(array, axis=0)


def encode_png(image_rgb: np.ndarray) -> bytes:
    buffer = BytesIO()
    Image.fromarray(image_rgb.astype(np.uint8), mode="RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def validate_plant_image(image_rgb: np.ndarray, min_plant_fraction: float = 0.05) -> tuple[bool, str, float]:
    """Validate if the uploaded image actually contains plant foliage."""
    import cv2

    if image_rgb is None or image_rgb.size == 0 or image_rgb.ndim != 3:
        return False, "Invalid or empty image uploaded.", 0.0

    image_uint8 = image_rgb.astype(np.uint8)
    hsv = cv2.cvtColor(image_uint8, cv2.COLOR_RGB2HSV)

    # Green & yellow-green foliage
    lower_green = np.array([18, 15, 15])
    upper_green = np.array([105, 255, 255])
    mask_green = cv2.inRange(hsv, lower_green, upper_green)

    # Diseased / brown / dry leaf tissue
    lower_brown = np.array([8, 15, 15])
    upper_brown = np.array([28, 255, 220])
    mask_brown = cv2.inRange(hsv, lower_brown, upper_brown)

    combined_mask = cv2.bitwise_or(mask_green, mask_brown)

    # ExG check
    img_float = image_uint8.astype(np.float32) / 255.0
    r, g, b = img_float[:, :, 0], img_float[:, :, 1], img_float[:, :, 2]
    exg = (2 * g) - r - b
    exg_mask = (exg > 0.02) & (g > b * 0.75)

    final_mask = (combined_mask > 0) | exg_mask
    plant_fraction = float(np.mean(final_mask))

    if plant_fraction < min_plant_fraction:
        return (
            False,
            "Invalid image: No valid plant foliage detected. Please upload a valid plant leaf image.",
            plant_fraction,
        )

    return True, "Valid plant leaf image.", plant_fraction
