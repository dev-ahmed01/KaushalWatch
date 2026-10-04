from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)


@dataclass
class Detection:
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float


@dataclass(frozen=True)
class DetectorInfo:
    backend: str
    mode: str
    authoritative: bool
    message: str


class Detector(Protocol):
    info: DetectorInfo

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class HogPersonDetector:
    """Zero-download fallback used by CI and degraded local runs."""

    info = DetectorInfo(
        backend="hog",
        mode="fallback",
        authoritative=False,
        message=(
            "HOG fallback active. Attendance conclusions are suspended until "
            "the validated YOLO/OpenVINO detector is available."
        ),
    )

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


class YoloPersonDetector:
    """Validated demo person detector used by the attendance benchmark stack."""

    def __init__(
        self,
        model_name: str = "yolo11n.pt",
        confidence: float = 0.35,
        iou: float = 0.50,
        imgsz: int = 640,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "YOLO detector selected but Ultralytics is unavailable. "
                "Install backend/requirements-yolo-demo.txt."
            ) from exc

        self.model_name = model_name
        self.confidence = float(confidence)
        self.iou = float(iou)
        self.imgsz = int(imgsz)
        self.model = YOLO(model_name)
        self.info = DetectorInfo(
            backend="yolo11",
            mode="primary",
            authoritative=True,
            message=(
                f"YOLO person detector active ({model_name}, conf={self.confidence:.2f}, "
                f"iou={self.iou:.2f}, imgsz={self.imgsz})."
            ),
        )

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            classes=[0],
            conf=self.confidence,
            iou=self.iou,
            imgsz=self.imgsz,
            verbose=False,
        )
        if not results:
            return []

        result = results[0]
        if result.boxes is None or len(result.boxes) == 0:
            return []

        boxes = result.boxes.xyxy.cpu().numpy().tolist()
        confidences = result.boxes.conf.cpu().numpy().tolist()

        detections: list[Detection] = []
        for box, confidence in zip(boxes, confidences):
            x1, y1, x2, y2 = [int(round(v)) for v in box]
            detections.append(
                Detection(
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    confidence=float(confidence),
                )
            )
        return detections


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
        self.info = DetectorInfo(
            backend="openvino",
            mode="primary",
            authoritative=True,
            message=(
                f"OpenVINO person detector active (device={device}, "
                f"confidence={self.confidence:.2f})."
            ),
        )

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


def _build_openvino() -> OpenVinoPersonDetector:
    xml = Path(
        os.getenv(
            "KAUSHALWATCH_OPENVINO_MODEL_XML",
            "../models/openvino/person-detection-retail-0013/FP16/person-detection-retail-0013.xml",
        )
    )
    confidence = float(os.getenv("KAUSHALWATCH_PERSON_CONFIDENCE", "0.45"))
    device = os.getenv("KAUSHALWATCH_OPENVINO_DEVICE", "CPU")
    return OpenVinoPersonDetector(xml, device=device, confidence=confidence)


def _build_yolo() -> YoloPersonDetector:
    return YoloPersonDetector(
        model_name=os.getenv("KAUSHALWATCH_YOLO_MODEL", "yolo11n.pt"),
        confidence=float(os.getenv("KAUSHALWATCH_PERSON_CONFIDENCE", "0.35")),
        iou=float(os.getenv("KAUSHALWATCH_PERSON_IOU", "0.50")),
        imgsz=int(os.getenv("KAUSHALWATCH_PERSON_IMGSZ", "640")),
    )


def build_person_detector() -> Detector:
    """Prefer the validated detector and expose any fallback explicitly."""

    backend = os.getenv("KAUSHALWATCH_PERSON_DETECTOR", "auto").strip().lower()

    if backend in {"yolo", "yolo11", "ultralytics"}:
        return _build_yolo()
    if backend == "openvino":
        return _build_openvino()
    if backend == "hog":
        LOGGER.warning("Explicit HOG fallback selected for person detection")
        return HogPersonDetector()
    if backend != "auto":
        raise ValueError(f"Unknown KAUSHALWATCH_PERSON_DETECTOR backend: {backend}")

    failures: list[str] = []

    try:
        detector = _build_yolo()
        LOGGER.info("Attendance detector selected: %s", detector.info.message)
        return detector
    except Exception as exc:  # pragma: no cover - optional runtime
        failures.append(f"YOLO unavailable: {exc}")
        LOGGER.warning("YOLO person detector unavailable", exc_info=True)

    openvino_xml = os.getenv("KAUSHALWATCH_OPENVINO_MODEL_XML")
    if openvino_xml:
        try:
            detector = _build_openvino()
            LOGGER.info("Attendance detector selected: %s", detector.info.message)
            return detector
        except Exception as exc:  # pragma: no cover - optional runtime
            failures.append(f"OpenVINO unavailable: {exc}")
            LOGGER.warning("OpenVINO person detector unavailable", exc_info=True)

    detector = HogPersonDetector()
    detail = "; ".join(failures) if failures else "Primary detector not configured"
    detector.info = DetectorInfo(
        backend="hog",
        mode="fallback",
        authoritative=False,
        message=(
            "Detector unavailable / fallback mode. "
            f"{detail}. Attendance conclusions are suspended."
        ),
    )
    LOGGER.error(detector.info.message)
    return detector


# Backward-compatible alias for existing imports.
PersonDetector = HogPersonDetector
