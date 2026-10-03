from __future__ import annotations

import argparse
from pathlib import Path
from urllib.request import urlretrieve

URL = "https://documents.epfl.ch/groups/c/cv/cvlab-pom-video1/www/6p-c0.avi"


def main() -> None:
    parser = argparse.ArgumentParser(description="Download EPFL Laboratory 6-person Camera 0 sequence.")
    parser.add_argument("--out", default="data/raw/epfl/6p-c0.avi")
    args = parser.parse_args()
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading research dataset footage to {target}")
    urlretrieve(URL, target)
    print("Done.")
    print("Usage note: EPFL CVLab states the dataset may be used for research purposes; cite the dataset/publication as required.")


if __name__ == "__main__":
    main()
