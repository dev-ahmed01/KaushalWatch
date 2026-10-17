"""Pure synthetic codec guards for private reference artifact handling."""
from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services.camera_reference_artifacts import (
    CameraReferencePolicyError, normalize_image, pixel_digest, object_key, config,
)


def sample():
    image=np.zeros((72,96,3),dtype=np.uint8)
    image[:,:,0]=np.arange(96,dtype=np.uint8)
    image[:,:,1]=np.arange(72,dtype=np.uint8)[:,None]
    image[:,:,2]=120
    return image


@pytest.mark.parametrize("extension",[".png",".jpg"])
def test_png_jpeg_normalized_to_integrity_checked_pixel_digest(extension):
    frame=sample()
    ok,encoded=cv2.imencode(extension,frame)
    assert ok
    pixels,normalized,digest,sha=normalize_image(encoded.tobytes())
    assert normalized.startswith(b"\x89PNG\r\n\x1a\n")
    assert digest==pixel_digest(pixels)
    assert digest!=sha


def test_png_declared_excessive_dimensions_fail_before_decode(monkeypatch):
    # Even though the total compressed request is tiny, declared dimensions
    # would otherwise induce a potentially huge allocation on decode.
    fake=(b"\x89PNG\r\n\x1a\n" + (13).to_bytes(4,"big") + b"IHDR" +
          (60000).to_bytes(4,"big") + (60000).to_bytes(4,"big") + b"\x00"*20)
    monkeypatch.setattr(cv2,"imdecode",lambda *_: (_ for _ in ()).throw(
        AssertionError("Should not call OpenCV decoder on oversized header")
    ))
    with pytest.raises(CameraReferencePolicyError,match="dimensions"):
        normalize_image(fake)


def test_alpha_png_is_normalized_to_three_channels():
    image=np.zeros((72,96,4),dtype=np.uint8)
    image[:,:,0]=20
    image[:,:,3]=255
    ok,blob=cv2.imencode(".png",image)
    assert ok
    decoded,canonical,_,_=normalize_image(blob.tobytes())
    assert decoded.shape == (72,96,3)
    assert canonical.startswith(b"\x89PNG\r\n\x1a\n")


def test_disabled_private_mode_does_not_make_network_calls(monkeypatch):
    monkeypatch.setenv("KAUSHALWATCH_ENV","production")
    monkeypatch.setenv("KAUSHALWATCH_CAMERA_REFERENCE_WORKFLOW","shadow_artifact")
    monkeypatch.setenv("KAUSHALWATCH_STORAGE_BACKEND","postgres")
    with pytest.raises(CameraReferencePolicyError,match="staging-only"):
        config()


def test_server_generated_object_key_refuses_untrusted_paths():
    with pytest.raises(CameraReferencePolicyError):
        object_key("centre/other","camera",1)
    with pytest.raises(CameraReferencePolicyError):
        object_key("centre","../camera",1)
    key=object_key("DEMO-KA-104","LAB-CAM-01",2)
    assert key.startswith("camera-references/v1/DEMO-KA-104/LAB-CAM-01/r2/")
    assert key.endswith(".png")
