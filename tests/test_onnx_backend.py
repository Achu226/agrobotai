"""The Raspberry Pi ONNX backend must give the same probabilities as the PyTorch wrapper (incl. TTA)."""
import numpy as np
import pytest

from src.config import MODELS_DIR

pytest.importorskip("onnxruntime")
ONNX = MODELS_DIR / "onnx" / "disease_model.onnx"


@pytest.mark.skipif(not ONNX.exists(), reason="run scripts/export_onnx.py first")
def test_onnx_matches_pytorch_with_and_without_tta():
    torch = pytest.importorskip("torch")
    from src.disease_detector import load_disease_model
    from src.onnx_backend import OnnxWrapper

    ref = load_disease_model()
    ref.model.to("cpu")
    ref.device, ref.mean, ref.std = torch.device("cpu"), ref.mean.cpu(), ref.std.cpu()
    onnx = OnnxWrapper(ONNX)
    batch = np.random.default_rng(0).random((1, 224, 224, 3), dtype=np.float32)
    for tta in (False, True):
        np.testing.assert_allclose(onnx.predict(batch, use_tta=tta), ref.predict(batch, use_tta=tta), atol=1e-4)
