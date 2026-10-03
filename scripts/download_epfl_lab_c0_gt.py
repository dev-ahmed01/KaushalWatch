from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

URL = (
    "https://raw.githubusercontent.com/vpulab/GNN-CCA/"
    "98cbbae41c777835b958e434192b8465d957b7f1/"
    "datasets/EPFL-Laboratory/laboratory6-c0/gt/gt.txt"
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download EPFL Laboratory Camera 0 bounding-box annotations used by GNN-CCA."
    )
    parser.add_argument("--out", default="data/raw/epfl/laboratory6-c0-gt.txt")
    args = parser.parse_args()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(URL, target)
    print(target)
    print(
        "Source is an external research-repository copy of EPFL annotations; "
        "do not commit the downloaded annotation file."
    )


if __name__ == "__main__":
    main()
