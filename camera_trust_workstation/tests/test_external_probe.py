import cv2
import json
import numpy as np
import pytest
from kwtrust.external_probe import probe,run,STATUS


def test_source_labeled_truth_is_never_fabricated(tmp_path):
    path=tmp_path/'test.avi'
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),10,(64,64))
    assert writer.isOpened()
    rng=np.random.default_rng(17);base=rng.integers(0,255,(64,64,3),dtype=np.uint8)
    for i in range(75):
        frame=cv2.GaussianBlur(base,(13,13),5) if i>40 else base
        writer.write(frame)
    writer.release()
    record=probe(path,sample_interval_seconds=1,max_samples=20)
    assert record['status']==STATUS
    assert record['source_video_has_independent_healthy_label'] is False
    assert record['camera_tampering_verified'] is False
    assert record['field_false_alarm_rate_established'] is False
    assert record['no_video_or_frames_exported'] is True
    assert record['exact_decoded_samples']>=7
    assert all(o['physical_camera_pose_verified'] is False for o in record['observations'])
    saved=tmp_path/'measurements.json'
    result=run([path],saved,interval=1,max_samples=20)
    assert saved.is_file()
    assert result['field_false_alarm_rate_established'] is False
    with pytest.raises(FileExistsError):run([path],saved)
