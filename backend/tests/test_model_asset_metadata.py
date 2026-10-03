import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "download_openvino_person_model.py"


def load_module():
    spec = importlib.util.spec_from_file_location("download_openvino_person_model", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_openvino_checksums_are_sha384_and_expected_values():
    module = load_module()
    assert module.FILES["person-detection-retail-0013.xml"] == (
        "99ad3d4580a0123bef05ff77b6f46ccec16de974d1f5699fb94cd842e3242c6aa641f4977f9a5bb2f0fab42fe51cbb63"
    )
    assert module.FILES["person-detection-retail-0013.bin"] == (
        "a67422e3b5ec76057651d2a0237eab862de00e968c7eef1e5f333849ae64f91900bcd30a23e1b7dbaa07313e358759b9"
    )
    assert all(len(value) == 96 for value in module.FILES.values())
