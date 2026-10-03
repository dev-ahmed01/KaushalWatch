from __future__ import annotations

from dataclasses import dataclass
import math

from app.services.person_detector import Detection


@dataclass
class AnonymousTrack:
    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    hits: int = 1
    missed: int = 0

    @property
    def centroid(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2.0, (self.y1 + self.y2) / 2.0)


class AnonymousCentroidTracker:
    """Short-lived positional tracker. IDs have no identity meaning outside the stream."""

    def __init__(self, max_distance: float = 140.0, max_missed: int = 2) -> None:
        self.max_distance = max_distance
        self.max_missed = max_missed
        self._next_id = 1
        self._tracks: dict[int, AnonymousTrack] = {}

    @property
    def tracks(self) -> list[AnonymousTrack]:
        return list(self._tracks.values())

    def reset(self) -> None:
        self._next_id = 1
        self._tracks.clear()

    def update(self, detections: list[Detection]) -> list[AnonymousTrack]:
        if not self._tracks:
            for det in detections:
                self._create(det)
            return self.tracks

        track_ids = list(self._tracks)
        unmatched_tracks = set(track_ids)
        unmatched_detections = set(range(len(detections)))
        candidates: list[tuple[float, int, int]] = []

        for track_id in track_ids:
            tx, ty = self._tracks[track_id].centroid
            for det_idx, det in enumerate(detections):
                dx = (det.x1 + det.x2) / 2.0
                dy = (det.y1 + det.y2) / 2.0
                distance = math.hypot(tx - dx, ty - dy)
                if distance <= self.max_distance:
                    candidates.append((distance, track_id, det_idx))

        # Greedy nearest-neighbour matching is sufficient for the small room-scale prototype.
        for _, track_id, det_idx in sorted(candidates):
            if track_id not in unmatched_tracks or det_idx not in unmatched_detections:
                continue
            det = detections[det_idx]
            track = self._tracks[track_id]
            track.x1, track.y1, track.x2, track.y2 = det.x1, det.y1, det.x2, det.y2
            track.hits += 1
            track.missed = 0
            unmatched_tracks.remove(track_id)
            unmatched_detections.remove(det_idx)

        for track_id in unmatched_tracks:
            self._tracks[track_id].missed += 1

        for track_id in [
            tid for tid, track in self._tracks.items()
            if track.missed > self.max_missed
        ]:
            del self._tracks[track_id]

        for det_idx in unmatched_detections:
            self._create(detections[det_idx])

        return self.tracks

    def _create(self, det: Detection) -> None:
        self._tracks[self._next_id] = AnonymousTrack(
            track_id=self._next_id,
            x1=det.x1,
            y1=det.y1,
            x2=det.x2,
            y2=det.y2,
        )
        self._next_id += 1
