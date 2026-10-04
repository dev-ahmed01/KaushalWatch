# Runtime model assets

Model weights/binaries are intentionally not committed.

Use `scripts/download_openvino_person_model.py` to place the lightweight OpenVINO pedestrian detector here. Experimental equipment-model weights should follow the same rule.

Code and model licences are separate; verify both before redistribution.


## Prepare the SIH person detector

From the repository root:

```bash
python scripts/prepare_demo_vision.py --install
```

The preparation command installs the optional OpenVINO runtime into the active Python
environment, downloads the checksum-verified model when needed, and verifies the XML/BIN
pair. KaushalWatch `auto` detector mode prefers this local benchmarked model when ready.
