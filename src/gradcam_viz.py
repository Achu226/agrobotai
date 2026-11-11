"""
Grad-CAM (Gradient-weighted Class Activation Mapping) Visualization
Shows which parts of the leaf image triggered the pest/disease detection
Builds farmer trust by making AI decisions transparent and interpretable
"""

from __future__ import annotations
import cv2
import numpy as np
import torch
import torch.nn.functional as F
from typing import Optional, Tuple
from PIL import Image


class GradCAM:
    """
    Grad-CAM visualization for PyTorch models
    Highlights discriminative regions used by CNN for classification
    """

    def __init__(self, model, target_layer):
        """
        Args:
            model: PyTorch model
            target_layer: Layer to compute gradients from (usually last conv layer)
        """
        self.model = model
        self.target_layer = target_layer
        self.gradients = None
        self.activations = None

        # Register hooks
        self.target_layer.register_forward_hook(self._forward_hook)
        self.target_layer.register_full_backward_hook(self._backward_hook)

    def _forward_hook(self, module, input, output):
        """Save forward pass activations"""
        self.activations = output.detach()

    def _backward_hook(self, module, grad_input, grad_output):
        """Save backward pass gradients"""
        self.gradients = grad_output[0].detach()

    def generate_cam(
        self,
        input_tensor: torch.Tensor,
        target_class: Optional[int] = None
    ) -> np.ndarray:
        """
        Generate Class Activation Map

        Args:
            input_tensor: Preprocessed input image tensor (1, C, H, W)
            target_class: Target class index (if None, use predicted class)

        Returns:
            Heatmap as numpy array (H, W) with values 0-1
        """
        self.model.eval()

        # Forward pass
        output = self.model(input_tensor)

        # Use predicted class if target not specified
        if target_class is None:
            target_class = output.argmax(dim=1).item()

        # Zero gradients
        self.model.zero_grad()

        # Backward pass for target class
        class_score = output[0, target_class]
        class_score.backward()

        # Get activations and gradients
        activations = self.activations[0]  # (C, H, W)
        gradients = self.gradients[0]  # (C, H, W)

        # Global average pooling of gradients
        weights = gradients.mean(dim=(1, 2), keepdim=True)  # (C, 1, 1)

        # Weighted combination of activation maps
        cam = (weights * activations).sum(dim=0)  # (H, W)

        # Apply ReLU (only positive contributions)
        cam = F.relu(cam)

        # Normalize to [0, 1]
        cam = cam.cpu().numpy()
        cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

        return cam

    def generate_visualization(
        self,
        original_image: np.ndarray,
        input_tensor: torch.Tensor,
        target_class: Optional[int] = None,
        alpha: float = 0.5
    ) -> np.ndarray:
        """
        Generate Grad-CAM heatmap overlay on original image

        Args:
            original_image: Original RGB image (H, W, 3) as numpy array
            input_tensor: Preprocessed tensor for model
            target_class: Target class (None = predicted class)
            alpha: Overlay transparency (0-1)

        Returns:
            RGB image with heatmap overlay
        """
        # Generate CAM
        cam = self.generate_cam(input_tensor, target_class)

        # Resize CAM to match original image size
        h, w = original_image.shape[:2]
        cam_resized = cv2.resize(cam, (w, h))

        # Convert to heatmap (jet colormap)
        heatmap = cv2.applyColorMap(
            (cam_resized * 255).astype(np.uint8),
            cv2.COLORMAP_JET
        )
        heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)

        # Overlay on original image
        overlay = (alpha * heatmap + (1 - alpha) * original_image).astype(np.uint8)

        return overlay


def generate_gradcam_for_detection(
    model,
    image_rgb: np.ndarray,
    preprocessing_fn,
    target_layer_name: str = "features",
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
) -> Tuple[np.ndarray, int, float]:
    """
    Convenience function to generate Grad-CAM for pest/disease detection

    Args:
        model: Trained PyTorch model
        image_rgb: Original RGB image
        preprocessing_fn: Function to preprocess image into tensor
        target_layer_name: Name of target convolutional layer
        device: cuda or cpu

    Returns:
        (gradcam_overlay, predicted_class, confidence)
    """
    model = model.to(device)
    model.eval()

    # Preprocess image
    input_tensor = preprocessing_fn(image_rgb).unsqueeze(0).to(device)

    # Get target layer
    target_layer = dict(model.named_modules())[target_layer_name]

    # Create Grad-CAM
    gradcam = GradCAM(model, target_layer)

    # Generate visualization
    overlay = gradcam.generate_visualization(
        original_image=image_rgb,
        input_tensor=input_tensor,
        alpha=0.6
    )

    # Get prediction
    with torch.no_grad():
        output = model(input_tensor)
        probabilities = F.softmax(output, dim=1)[0]
        confidence, predicted_class = probabilities.max(dim=0)

    return overlay, predicted_class.item(), confidence.item()


def gradcam_with_bounding_boxes(
    gradcam_overlay: np.ndarray,
    cam_threshold: float = 0.5
) -> np.ndarray:
    """
    Add bounding boxes around high-activation regions

    Args:
        gradcam_overlay: Grad-CAM visualization
        cam_threshold: Threshold for high activation (0-1)

    Returns:
        Image with bounding boxes drawn
    """
    # Convert to grayscale to find contours
    gray = cv2.cvtColor(gradcam_overlay, cv2.COLOR_RGB2GRAY)

    # Threshold to find high-activation regions
    _, thresh = cv2.threshold(
        gray,
        int(cam_threshold * 255),
        255,
        cv2.THRESH_BINARY
    )

    # Find contours
    contours, _ = cv2.findContours(
        thresh,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    # Draw bounding boxes
    result = gradcam_overlay.copy()
    for contour in contours:
        if cv2.contourArea(contour) > 100:  # Filter small noise
            x, y, w, h = cv2.boundingRect(contour)
            cv2.rectangle(result, (x, y), (x + w, y + h), (255, 255, 0), 2)

    return result


# Example usage for timm models (ConvNeXt, EfficientNet, etc.)
def get_target_layer_for_model(model, model_name: str):
    """
    Get the appropriate target layer for common architectures

    Args:
        model: PyTorch model
        model_name: Model architecture name

    Returns:
        Target layer object
    """
    # torchvision EfficientNet / EfficientNetV2 / ConvNeXt all expose `features`
    if hasattr(model, "features") and ("convnext" in model_name.lower() or "efficientnet" in model_name.lower()):
        return model.features[-1]
    if "convnext" in model_name.lower():
        # timm ConvNeXt: last stage
        return model.stages[-1]
    elif "efficientnet" in model_name.lower():
        # timm EfficientNet: last conv block
        return model.conv_head if hasattr(model, 'conv_head') else model.blocks[-1]
    elif "resnet" in model_name.lower():
        # ResNet: layer4
        return model.layer4
    elif "swin" in model_name.lower():
        # Swin Transformer: last layer
        return model.layers[-1]
    else:
        # Generic fallback: try to find last conv layer
        conv_layers = [m for m in model.modules() if isinstance(m, torch.nn.Conv2d)]
        return conv_layers[-1] if conv_layers else None


def find_target_layer(model):
    """Last spatial feature block of a torchvision CNN, else the last Conv2d."""
    features = getattr(model, "features", None)
    if isinstance(features, torch.nn.Sequential) and len(features) > 0:
        return features[-1]
    conv_layers = [m for m in model.modules() if isinstance(m, torch.nn.Conv2d)]
    return conv_layers[-1] if conv_layers else None


def _encode_jpeg_data_url(image_rgb: np.ndarray, quality: int = 85) -> str:
    import base64

    ok, buf = cv2.imencode(".jpg", cv2.cvtColor(image_rgb, cv2.COLOR_RGB2BGR), [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("Failed to encode Grad-CAM image")
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("utf-8")


def gradcam_for_wrapper(
    wrapper,
    image_rgb: np.ndarray,
    class_index: Optional[int] = None,
    alpha: float = 0.45,
    max_side: int = 512,
) -> dict:
    """
    Grad-CAM for the PyTorchDiseaseWrapper / PyTorchPestWrapper used by the app.

    Hooks are attached for a single pass and removed afterwards, so this is safe
    to call repeatedly on the cached models.
    """
    from src.image_utils import prepare_model_input

    model = wrapper.model
    target_layer = find_target_layer(model)
    if target_layer is None:
        raise RuntimeError("No convolutional layer found for Grad-CAM")

    batch = prepare_model_input(image_rgb)
    tensor = torch.from_numpy(batch).permute(0, 3, 1, 2).float().to(wrapper.device)
    norm = (tensor - wrapper.mean) / wrapper.std

    store = {}

    def _forward_hook(module, inputs, output):
        store["activations"] = output
        output.register_hook(lambda grad: store.__setitem__("gradients", grad))

    handle = target_layer.register_forward_hook(_forward_hook)
    try:
        model.eval()
        with torch.enable_grad():
            model.zero_grad(set_to_none=True)
            logits = model(norm)
            probs = F.softmax(logits, dim=1)[0].detach()
            idx = int(probs.argmax()) if class_index is None else int(class_index)
            logits[0, idx].backward()
    finally:
        handle.remove()
        model.zero_grad(set_to_none=True)

    activations = store["activations"][0].detach()
    gradients = store["gradients"][0].detach()
    weights = gradients.mean(dim=(1, 2), keepdim=True)
    cam = F.relu((weights * activations).sum(dim=0)).cpu().numpy()
    cam = (cam - cam.min()) / (cam.max() - cam.min() + 1e-8)

    # Downscale large photos so the base64 payload stays small
    h, w = image_rgb.shape[:2]
    scale = min(1.0, max_side / max(h, w))
    base = image_rgb.astype(np.uint8)
    if scale < 1.0:
        base = cv2.resize(base, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    bh, bw = base.shape[:2]

    cam_resized = cv2.resize(cam.astype(np.float32), (bw, bh))
    heatmap = cv2.cvtColor(cv2.applyColorMap((cam_resized * 255).astype(np.uint8), cv2.COLORMAP_JET), cv2.COLOR_BGR2RGB)
    overlay = (alpha * heatmap + (1 - alpha) * base).astype(np.uint8)

    # Outline the strongest-attention regions
    hot = (cam_resized >= 0.6).astype(np.uint8) * 255
    contours, _ = cv2.findContours(hot, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    min_area = 0.005 * bh * bw
    cv2.drawContours(overlay, [c for c in contours if cv2.contourArea(c) >= min_area], -1, (255, 255, 255), 2)

    return {
        "ok": True,
        "class_index": idx,
        "confidence": round(float(probs[idx]) * 100.0, 2),
        "focus_area_pct": round(float((cam_resized >= 0.6).mean()) * 100.0, 1),
        "heatmap_base64": _encode_jpeg_data_url(overlay),
        "overlay": overlay,
    }


if __name__ == "__main__":
    print("Grad-CAM module loaded successfully")
    print("Use generate_gradcam_for_detection() to create explainable visualizations")
