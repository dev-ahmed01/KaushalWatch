from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

LOGGER = logging.getLogger(__name__)
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OPENVINO_XML = REPO_ROOT / "models" / "openvino" / "person-detection-retail-0013" / "FP16" / "person-detection-retail-0013.xml"


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
            "HOG fallback active. Automated compliance conclusions are suspended until "
            "a validated YOLO/OpenVINO person detector is available."
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


def _intersection_over_union(a: Detection, b: Detection) -> float:
    x1 = max(a.x1, b.x1)
    y1 = max(a.y1, b.y1)
    x2 = min(a.x2, b.x2)
    y2 = min(a.y2, b.y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    intersection = float((x2 - x1) * (y2 - y1))
    area_a = float(max(0, a.x2 - a.x1) * max(0, a.y2 - a.y1))
    area_b = float(max(0, b.x2 - b.x1) * max(0, b.y2 - b.y1))
    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


def _nms_detections(
    detections: list[Detection],
    iou_threshold: float = 0.45,
) -> list[Detection]:
    kept: list[Detection] = []
    for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
        if any(
            _intersection_over_union(detection, existing) >= iou_threshold
            for existing in kept
        ):
            continue
        kept.append(detection)
    return kept


def _tile_windows(
    width: int,
    height: int,
    overlap: float = 0.18,
) -> list[tuple[int, int, int, int]]:
    """Return four overlapping 2x2 windows for recall-oriented secondary inference."""

    overlap = min(0.45, max(0.0, float(overlap)))
    tile_w = int(round(width / (2.0 - overlap)))
    tile_h = int(round(height / (2.0 - overlap)))
    tile_w = min(width, max(1, tile_w))
    tile_h = min(height, max(1, tile_h))
    x_positions = [0, max(0, width - tile_w)]
    y_positions = [0, max(0, height - tile_h)]
    return [
        (x, y, min(width, x + tile_w), min(height, y + tile_h))
        for y in y_positions
        for x in x_positions
    ]


class OpenVinoPersonDetector:
    """Open Model Zoo person detector with optional recall-oriented tiled inference."""

    def __init__(
        self,
        model_xml: Path,
        device: str = "CPU",
        confidence: float = 0.45,
        tiled: bool = False,
        tile_overlap: float = 0.18,
        tile_nms_iou: float = 0.45,
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

        self.confidence = float(confidence)
        self.tiled = bool(tiled)
        self.tile_overlap = float(tile_overlap)
        self.tile_nms_iou = float(tile_nms_iou)
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
                f"confidence={self.confidence:.2f}, "
                f"tiled={'on' if self.tiled else 'off'})."
            ),
        )

    def _infer_region(
        self,
        frame: np.ndarray,
        *,
        offset_x: int = 0,
        offset_y: int = 0,
    ) -> list[Detection]:
        h, w = frame.shape[:2]
        resized = cv2.resize(frame, (self.input_w, self.input_h))
        tensor = resized.transpose(2, 0, 1)[None, ...].astype(np.float32)
        result = self.compiled([tensor])[self.output_layer]
        detections: list[Detection] = []

        for row in result.reshape(-1, 7):
            image_id, label, conf, x_min, y_min, x_max, y_max = [float(v) for v in row]
            if image_id < 0 or int(label) != 1 or conf < self.confidence:
                continue
            local_x1 = max(0, min(w - 1, int(x_min * w)))
            local_y1 = max(0, min(h - 1, int(y_min * h)))
            local_x2 = max(0, min(w, int(x_max * w)))
            local_y2 = max(0, min(h, int(y_max * h)))
            if local_x2 <= local_x1 or local_y2 <= local_y1:
                continue
            detections.append(
                Detection(
                    x1=local_x1 + offset_x,
                    y1=local_y1 + offset_y,
                    x2=local_x2 + offset_x,
                    y2=local_y2 + offset_y,
                    confidence=conf,
                )
            )
        return detections

    def detect(self, frame: np.ndarray) -> list[Detection]:
        detections = self._infer_region(frame)
        if not self.tiled:
            return detections

        height, width = frame.shape[:2]
        for x1, y1, x2, y2 in _tile_windows(
            width,
            height,
            overlap=self.tile_overlap,
        ):
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            detections.extend(
                self._infer_region(crop, offset_x=x1, offset_y=y1)
            )

        return _nms_detections(detections, self.tile_nms_iou)


def _resolve_openvino_xml() -> Path:
    raw = os.getenv("KAUSHALWATCH_OPENVINO_MODEL_XML")
    if not raw:
        return DEFAULT_OPENVINO_XML

    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate

    repo_relative = (REPO_ROOT / candidate).resolve()
    if repo_relative.exists():
        return repo_relative

    backend_relative = (REPO_ROOT / "backend" / candidate).resolve()
    if backend_relative.exists():
        return backend_relative

    return repo_relative


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _build_openvino() -> OpenVinoPersonDetector:
    xml = _resolve_openvino_xml()
    confidence = float(os.getenv("KAUSHALWATCH_PERSON_CONFIDENCE", "0.45"))
    device = os.getenv("KAUSHALWATCH_OPENVINO_DEVICE", "CPU")
    tiled = _env_flag("KAUSHALWATCH_OPENVINO_TILED", False)
    tile_overlap = float(os.getenv("KAUSHALWATCH_OPENVINO_TILE_OVERLAP", "0.18"))
    tile_nms_iou = float(os.getenv("KAUSHALWATCH_OPENVINO_TILE_NMS_IOU", "0.45"))
    return OpenVinoPersonDetector(
        xml,
        device=device,
        confidence=confidence,
        tiled=tiled,
        tile_overlap=tile_overlap,
        tile_nms_iou=tile_nms_iou,
    )


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

    # The SIH demo is benchmarked against the local OpenVINO model. Prefer it
    # whenever the verified model files are present so an installed Ultralytics
    # package cannot silently change the demo detector.
    openvino_xml = _resolve_openvino_xml()
    if openvino_xml.exists():
        try:
            detector = _build_openvino()
            LOGGER.info("Person detector selected: %s", detector.info.message)
            return detector
        except Exception as exc:  # pragma: no cover - optional runtime
            failures.append(f"OpenVINO unavailable: {exc}")
            LOGGER.warning("OpenVINO person detector unavailable", exc_info=True)
    else:
        failures.append(
            "OpenVINO demo model is not prepared at "
            f"{openvino_xml}"
        )

    try:
        detector = _build_yolo()
        LOGGER.info("Person detector selected: %s", detector.info.message)
        return detector
    except Exception as exc:  # pragma: no cover - optional runtime
        failures.append(f"YOLO unavailable: {exc}")
        LOGGER.warning("YOLO person detector unavailable", exc_info=True)

    detector = HogPersonDetector()
    detail = "; ".join(failures) if failures else "Primary detector not configured"
    detector.info = DetectorInfo(
        backend="hog",
        mode="fallback",
        authoritative=False,
        message=(
            "Validated person detector unavailable / fallback mode. "
            f"{detail}. Run 'python scripts/prepare_demo_vision.py --install' "
            "for the benchmarked OpenVINO demo detector. Automated compliance "
            "conclusions are suspended."
        ),
    )
    LOGGER.error(detector.info.message)
    return detector


# Backward-compatible alias for existing imports.
PersonDetector = HogPersonDetector
