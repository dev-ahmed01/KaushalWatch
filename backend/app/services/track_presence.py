from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class TrackObservation:
    """One anonymous tracker observation at a point in time."""

    track_id: int
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float | None = None
    zone_id: str | None = None


@dataclass
class PresenceTrack:
    """Temporal state for one anonymous in-stream track.

    Track IDs are session-local positional identifiers only. They are not
    biometric identities and must not be reused across independent runs.
    """

    track_id: int
    first_seen_at: float
    last_seen_at: float
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float | None = None
    visible_seconds: float = 0.0
    missed_seconds: float = 0.0
    confirmed_at: float | None = None
    registered_at: float | None = None
    status: str = "tentative"
    zone_id: str | None = None
    zone_dwell_seconds: float = 0.0

    @property
    def confirmed(self) -> bool:
        return self.confirmed_at is not None

    @property
    def registered(self) -> bool:
        return self.registered_at is not None

    @property
    def active(self) -> bool:
        return self.status != "ended"

    @property
    def bbox(self) -> tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


class TrackPresenceRegistry:
    """Filter transient tracks before they affect attendance occupancy.

    Lifecycle:
        tentative -> confirmed -> registered -> ended

    The registry expects anonymous tracker IDs from a short-lived tracker such
    as ByteTrack or AnonymousCentroidTracker. Short detector flashes never
    become attendance-registered unless they survive the stricter registration
    threshold. Brief dropouts are bridged for a bounded grace period.

    No identity inference is performed here.
    """

    def __init__(
        self,
        confirmation_seconds: float = 1.0,
        registration_seconds: float = 2.0,
        grace_seconds: float = 0.8,
    ) -> None:
        if confirmation_seconds < 0:
            raise ValueError("confirmation_seconds must be >= 0")
        if registration_seconds < confirmation_seconds:
            raise ValueError(
                "registration_seconds must be >= confirmation_seconds"
            )
        if grace_seconds < 0:
            raise ValueError("grace_seconds must be >= 0")

        self.confirmation_seconds = float(confirmation_seconds)
        self.registration_seconds = float(registration_seconds)
        self.grace_seconds = float(grace_seconds)
        self._tracks: dict[int, PresenceTrack] = {}
        self._last_timestamp: float | None = None

    @property
    def tracks(self) -> list[PresenceTrack]:
        return list(self._tracks.values())

    @property
    def active_tracks(self) -> list[PresenceTrack]:
        return [track for track in self._tracks.values() if track.active]

    @property
    def tentative_tracks(self) -> list[PresenceTrack]:
        return [track for track in self.active_tracks if not track.confirmed]

    @property
    def confirmed_tracks(self) -> list[PresenceTrack]:
        return [track for track in self.active_tracks if track.confirmed]

    @property
    def registered_tracks(self) -> list[PresenceTrack]:
        return [track for track in self.active_tracks if track.registered]

    @property
    def candidate_count(self) -> int:
        return len(self.tentative_tracks)

    @property
    def confirmed_count(self) -> int:
        return len(self.confirmed_tracks)

    @property
    def registered_count(self) -> int:
        return len(self.registered_tracks)

    def reset(self) -> None:
        self._tracks.clear()
        self._last_timestamp = None

    def update(
        self,
        timestamp: float,
        observations: Iterable[TrackObservation],
    ) -> list[PresenceTrack]:
        timestamp = float(timestamp)
        if timestamp < 0:
            raise ValueError("timestamp must be >= 0")
        if self._last_timestamp is not None and timestamp < self._last_timestamp:
            raise ValueError("timestamps must be monotonically non-decreasing")

        dt = (
            0.0
            if self._last_timestamp is None
            else timestamp - self._last_timestamp
        )
        self._last_timestamp = timestamp

        observations_by_id = {obs.track_id: obs for obs in observations}
        observed_ids = set(observations_by_id)

        # Age tracks that were not observed in this update. A short miss does not
        # immediately erase a real person from the stable occupancy count.
        for track in self.active_tracks:
            if track.track_id not in observed_ids:
                track.missed_seconds += dt
                if track.missed_seconds > self.grace_seconds:
                    track.status = "ended"
                    track.zone_id = None
                    track.zone_dwell_seconds = 0.0

        for track_id, obs in observations_by_id.items():
            track = self._tracks.get(track_id)

            if track is None or not track.active:
                track = PresenceTrack(
                    track_id=track_id,
                    first_seen_at=timestamp,
                    last_seen_at=timestamp,
                    x1=obs.x1,
                    y1=obs.y1,
                    x2=obs.x2,
                    y2=obs.y2,
                    confidence=obs.confidence,
                    zone_id=obs.zone_id,
                )
                self._tracks[track_id] = track
            else:
                continuously_visible = track.missed_seconds == 0.0
                track.x1 = obs.x1
                track.y1 = obs.y1
                track.x2 = obs.x2
                track.y2 = obs.y2
                track.confidence = obs.confidence
                track.last_seen_at = timestamp

                # Never credit detector gaps as visible attendance time.
                if continuously_visible:
                    track.visible_seconds += dt

                if obs.zone_id is None:
                    track.zone_id = None
                    track.zone_dwell_seconds = 0.0
                elif obs.zone_id == track.zone_id:
                    if continuously_visible:
                        track.zone_dwell_seconds += dt
                else:
                    track.zone_id = obs.zone_id
                    track.zone_dwell_seconds = 0.0

                track.missed_seconds = 0.0

            self._promote(track, timestamp)

        return self.active_tracks

    def _promote(self, track: PresenceTrack, timestamp: float) -> None:
        if (
            track.confirmed_at is None
            and track.visible_seconds >= self.confirmation_seconds
        ):
            track.confirmed_at = timestamp
            track.status = "confirmed"

        if (
            track.registered_at is None
            and track.visible_seconds >= self.registration_seconds
        ):
            track.registered_at = timestamp
            track.status = "registered"

        if track.confirmed_at is None:
            track.status = "tentative"

    def get(self, track_id: int) -> PresenceTrack | None:
        return self._tracks.get(track_id)
