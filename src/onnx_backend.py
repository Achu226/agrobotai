"""
ONNX Runtime backend for devices without PyTorch (Raspberry Pi 4).

Runs the same EfficientNetV2-S weights exported by scripts/export_onnx.py. predict() mirrors
PyTorchDiseaseWrapper / PyTorchPestWrapper exactly (ImageNet normalisation, same 5-view TTA).
"""
from __future__ import annotations

import cv2
import numpy as np

MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)


def _softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def _crop_resize(batch: np.ndarray, start: int, end: int) -> np.ndarray:
    # cv2 INTER_LINEAR == torch bilinear with align_corners=False; resizing commutes with the
    # per-channel normalisation, so it is done on the raw NHWC image.
    return np.stack([cv2.resize(img[start:end, start:end], (224, 224), interpolation=cv2.INTER_LINEAR) for img in batch])


class OnnxWrapper:
    onnx = True

    def __init__(self, path, use_tta: bool = True, threads: int | None = None):
        import onnxruntime as ort

        opts = ort.SessionOptions()
        if threads:
            opts.intra_op_num_threads = threads
        self.session = ort.InferenceSession(str(path), opts, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.use_tta = use_tta
        self.device = "cpu (onnxruntime)"

    def logits(self, batch_nhwc: np.ndarray) -> np.ndarray:
        x = (np.asarray(batch_nhwc, dtype=np.float32).transpose(0, 3, 1, 2) - MEAN) / STD
        return self.session.run(None, {self.input_name: np.ascontiguousarray(x, dtype=np.float32)})[0]

    def predict(self, batch_numpy: np.ndarray, verbose=0, use_tta: bool | None = None) -> np.ndarray:
        batch = np.asarray(batch_numpy, dtype=np.float32)
        if not (self.use_tta if use_tta is None else use_tta):
            return _softmax(self.logits(batch))
        views = np.concatenate([batch, batch[:, :, ::-1], batch[:, ::-1],
                                _crop_resize(batch, 16, 208), _crop_resize(batch, 8, 216)])
        return _softmax(self.logits(views)).mean(axis=0, keepdims=True)
