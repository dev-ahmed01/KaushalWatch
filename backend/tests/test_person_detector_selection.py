import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import app.services.person_detector as detector_module
from app.services.person_detector import DetectorInfo


class _Detector:
    def __init__(self, backend: str):
        self.info = DetectorInfo(
            backend=backend,
            mode="primary",
            authoritative=True,
            message=f"{backend} test detector",
        )

    def detect(self, frame):
        return []


def test_auto_prefers_local_openvino_over_yolo(tmp_path, monkeypatch):
    xml = tmp_path / "person.xml"
    xml.write_text("<xml/>", encoding="utf-8")
    monkeypatch.delenv("KAUSHALWATCH_PERSON_DETECTOR", raising=False)
    monkeypatch.setattr(detector_module, "_resolve_openvino_xml", lambda: xml)
    monkeypatch.setattr(detector_module, "_build_openvino", lambda: _Detector("openvino"))
    monkeypatch.setattr(detector_module, "_build_yolo", lambda: _Detector("yolo11"))

    detector = detector_module.build_person_detector()

    assert detector.info.backend == "openvino"
    assert detector.info.authoritative is True


def test_auto_uses_yolo_when_local_openvino_model_is_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("KAUSHALWATCH_PERSON_DETECTOR", raising=False)
    monkeypatch.setattr(
        detector_module,
        "_resolve_openvino_xml",
        lambda: tmp_path / "missing.xml",
    )
    monkeypatch.setattr(detector_module, "_build_yolo", lambda: _Detector("yolo11"))

    detector = detector_module.build_person_detector()

    assert detector.info.backend == "yolo11"


def test_default_openvino_model_path_is_repo_root_relative():
    expected = (
        detector_module.REPO_ROOT
        / "models"
        / "openvino"
        / "person-detection-retail-0013"
        / "FP16"
        / "person-detection-retail-0013.xml"
    )
    assert detector_module.DEFAULT_OPENVINO_XML == expected
