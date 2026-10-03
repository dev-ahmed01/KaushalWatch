from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
from urllib.request import urlretrieve

BASE = "https://storage.openvinotoolkit.org/repositories/open_model_zoo/2023.0/models_bin/1/person-detection-retail-0013/FP16"

# SHA-384 values copied from openvinotoolkit/open_model_zoo model.yml.
FILES = {
    "person-detection-retail-0013.xml": "99ad3d4580a0123bef05ff77b6f46ccec16de974d1f5699fb94cd842e3242c6aa641f4977f9a5bb2f0fab42fe51cbb63",
    "person-detection-retail-0013.bin": "a67422e3b5ec76057651d2a0237eab862de00e968c7eef1e5f333849ae64f91900bcd30a23e1b7dbaa07313e358759b9",
}


def sha384(path: Path) -> str:
    h = hashlib.sha384()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default="models/openvino/person-detection-retail-0013/FP16",
        help="Destination directory",
    )
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    for name, checksum in FILES.items():
        target = out / name
        if target.exists() and sha384(target) == checksum:
            print(f"ok: {target}")
            continue

        url = f"{BASE}/{name}"
        print(f"downloading {url}")
        urlretrieve(url, target)
        actual = sha384(target)
        if actual != checksum:
            target.unlink(missing_ok=True)
            raise SystemExit(
                f"checksum mismatch for {name}: expected={checksum} actual={actual}"
            )
        print(f"verified: {target}")

    print(
        "Model downloaded. Open Model Zoo code/model licensing information "
        "must be retained when redistributed."
    )


if __name__ == "__main__":
    main()
