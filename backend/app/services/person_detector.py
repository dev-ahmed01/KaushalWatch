from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


class Detector(Protocol):
    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class HogPersonDetector:
    """Zero-download fallback used by core CI, not the final SIH benchmark detector."""

    def __init__(self) -> None:
        self.hog = cv2.HOGDescriptor()
        self.hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        target_w = min(w, 960)
        scale = target_w / w
        img = cv2.resize(frame, (target_w, int(h * scale))) if scale < 1 else frame
        rects, weights = self.hog.detectMultiScale(
            img, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        inv = 1 / scale if scale else 1
        return [
            Detection(
                int(x * inv),
                int(y * inv),
                int((x + rw) * inv),
                int((y + rh) * inv),
                float(weight),
            )
            for (x, y, rw, rh), weight in zip(rects, weights)
        ]


class OpenVinoPersonDetector:
    """Lightweight person detector backed by Open Model Zoo person-detection-retail-0013."""

    def __init__(
        self,
        model_xml: Path,
        device: str = "CPU",
        confidence: float = 0.45,
    ) -> None:
        try:
            import openvino as ov
        except ImportError as exc:
            raise RuntimeError(
                "OpenVINO detector selected but optional dependencies are missing. "
                "Install backend/requirements-vision.txt."
            ) from exc

        if not model_xml.exists():
            raise FileNotFoundError(
                f"OpenVINO model not found at {model_xml}. "
                "Run scripts/download_openvino_person_model.py first."
            )

        self.confidence = confidence
        core = ov.Core()
        model = core.read_model(model=str(model_xml))
        self.compiled = core.compile_model(model=model, device_name=device)
        self.input_layer = self.compiled.input(0)
        self.output_layer = self.compiled.output(0)
        shape = list(self.input_layer.shape)
        if len(shape) != 4:
            raise RuntimeError(f"Unexpected detector input shape: {shape}")
        _, _, self.input_h, self.input_w = [int(x) for x in shape]

    def detect(self, frame: np.ndarray) -> list[Detection]:
        h, w = frame.shape[:2]
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        tensor = resized.transpose(2, 0, 1)[None, ...].astype(np.float32)
        result = self.compiled([tensor])[self.output_layer]
        detections: list[Detection] = []

        for row in result.reshape(-1, 7):
            image_id, label, conf, x_min, y_min, x_max, y_max = [float(v) for v in row]
            if image_id < 0 or int(label) != 1 or conf < self.confidence:
                continue
            detections.append(
                Detection(
                    x1=max(0, min(w - 1, int(x_min * w))),
                    y1=max(0, min(h - 1, int(y_min * h))),
                    x2=max(0, min(w, int(x_max * w))),
                    y2=max(0, min(h, int(y_max * h))),
                    confidence=conf,
                )
            )
        return detections


def build_person_detector() -> Detector:
    backend = os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "hog").strip().lower()
    if backend == "hog":
        return HogPersonDetector()
    if backend == "openvino":
        xml = Path(
            os.getenv(
                "KAUSHALWATCH_OPENVINO_MODEL_XML",
                "../models/openvino/person-detection-retail-0013/FP16/person-detection-retail-0013.xml",
            )
        )
        confidence = float(os.getenv("KAUSHALWATCH_PERSON_CONFIDENCE", "0.45"))
        device = os.getenv("KAUSHALWATCH_OPENVINO_DEVICE", "CPU")
        return OpenVinoPersonDetector(xml, device=device, confidence=confidence)
    raise ValueError(f"Unknown KAUSHALWATCH_PERSON_DETECTOR backend: {backend}")


# Backward-compatible alias for existing imports.
PersonDetector = HogPersonDetector
