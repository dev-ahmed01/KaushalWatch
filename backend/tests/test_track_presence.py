import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.track_presence import TrackObservation, TrackPresenceRegistry


def obs(track_id: int = 1, zone_id: str | None = None) -> TrackObservation:
    return TrackObservation(
        track_id=track_id,
        x1=10,
        y1=10,
        x2=30,
        y2=60,
        confidence=0.9,
        zone_id=zone_id,
    )


def test_one_second_transient_is_not_attendance_registered():
    registry = TrackPresenceRegistry(
        confirmation_seconds=1.0,
        registration_seconds=2.0,
        grace_seconds=0.8,
    )

    for i in range(11):
        registry.update(i * 0.1, [obs()])

    track = registry.get(1)
    assert track is not None
    assert track.confirmed
    assert not track.registered
    assert registry.registered_count == 0


def test_two_second_stable_track_registers_for_attendance():
    registry = TrackPresenceRegistry(
        confirmation_seconds=1.0,
        registration_seconds=2.0,
        grace_seconds=0.8,
    )

    # A small epsilon avoids floating-point representation at exactly 2.0s.
    for i in range(22):
        registry.update(i * 0.1, [obs()])

    track = registry.get(1)
    assert track is not None
    assert track.confirmed
    assert track.registered
    assert registry.registered_count == 1


def test_brief_dropout_keeps_track_without_crediting_gap_as_visible_time():
    registry = TrackPresenceRegistry(
        confirmation_seconds=0.5,
        registration_seconds=1.0,
        grace_seconds=0.5,
    )

    for i in range(6):
        registry.update(i * 0.1, [obs()])

    track = registry.get(1)
    assert track is not None
    before = track.visible_seconds

    registry.update(0.6, [])
    registry.update(0.7, [])
    registry.update(0.8, [obs()])

    track = registry.get(1)
    assert track is not None
    assert track.active
    assert track.visible_seconds == pytest.approx(before)


def test_long_dropout_ends_track():
    registry = TrackPresenceRegistry(
        confirmation_seconds=0.5,
        registration_seconds=1.0,
        grace_seconds=0.3,
    )

    for i in range(6):
        registry.update(i * 0.1, [obs()])

    registry.update(0.6, [])
    registry.update(0.7, [])
    registry.update(0.8, [])
    registry.update(0.9, [])

    track = registry.get(1)
    assert track is not None
    assert not track.active
    assert registry.registered_count == 0


def test_zone_timer_requires_continuous_zone_presence():
    registry = TrackPresenceRegistry(
        confirmation_seconds=0.2,
        registration_seconds=0.4,
        grace_seconds=0.3,
    )

    registry.update(0.0, [obs(zone_id="Z2")])
    registry.update(0.1, [obs(zone_id="Z2")])
    registry.update(0.2, [obs(zone_id="Z2")])

    track = registry.get(1)
    assert track is not None
    assert track.zone_dwell_seconds == pytest.approx(0.2)

    registry.update(0.3, [obs(zone_id=None)])
    track = registry.get(1)
    assert track is not None
    assert track.zone_dwell_seconds == 0.0

    registry.update(0.4, [obs(zone_id="Z2")])
    track = registry.get(1)
    assert track is not None
    assert track.zone_dwell_seconds == 0.0


def test_tentative_track_does_not_inflate_registered_count():
    registry = TrackPresenceRegistry(
        confirmation_seconds=1.0,
        registration_seconds=2.0,
        grace_seconds=0.8,
    )

    # Real worker has already matured.
    for i in range(22):
        registry.update(i * 0.1, [obs(track_id=1)])

    # A new false positive appears next to the real worker.
    registry.update(2.2, [obs(track_id=1), obs(track_id=99)])

    assert registry.registered_count == 1
    assert registry.candidate_count == 1
