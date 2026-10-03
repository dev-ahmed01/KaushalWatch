# KaushalWatch Privacy-Preserving Design Note

## Purpose
KaushalWatch verifies training-centre attendance and visible infrastructure compliance while minimizing collection of personal data. The system is designed for aggregate compliance monitoring, not identification or surveillance of individual trainees.

## What the system observes
- Anonymous person detections inside configured classroom/workshop zones.
- Temporary tracker IDs used only to stabilize counts across adjacent video frames.
- Aggregate physical occupancy estimates.
- Presence of configured infrastructure items.
- Limited visual activity proxies for selected equipment, such as motion inside a machine region or an indicator state.
- Camera-health signals such as frozen feed, blur, darkness, obstruction, or viewpoint shift.

**No current compliance check in this system requires individual identification; any future check that did would require separate, explicit authorization outside this prototype's scope.**

## What the system does not identify in the prototype
- No facial recognition.
- No face embeddings.
- No biometric templates.
- No Aadhaar or other identity matching from video.
- No cross-camera person re-identification.
- No attempt to infer sensitive personal attributes from appearance.

## Tracking position, not identity
Temporary tracker IDs exist only to avoid double counting and to estimate stable occupancy. They represent short-lived trajectories such as `track_17`, not a person's identity. Tracker IDs are discarded after the configured processing window/session and are not linked to names or attendance identities.

## Edge-first processing
The intended deployment processes ordinary video locally at the training centre or approved edge device. The central monitoring service normally receives compact compliance telemetry such as centre/camera ID, timestamp, aggregate occupancy, expected/reported values, infrastructure counts, camera-health state and case metadata.

Continuous raw video is not required to leave the edge for normal operation.

## Evidence minimization
When a persistent discrepancy is detected, the system may retain only the minimum evidence needed for authorized review: a selected frame or short event clip plus structured metadata. Evidence is linked to a case ID and integrity hash. Faces should be blurred before centrally storing or sharing retained evidence where operationally feasible.

## Human-in-the-loop decision making
KaushalWatch does not automatically penalize a training centre. It produces machine states such as `COMPLIANT`, `DISCREPANCY`, and `UNCERTAIN`. Persistent discrepancies and uncertain cases are routed to an authorized monitoring officer, who may dismiss the event, confirm it, request virtual verification, or escalate to physical inspection.

## Equipment operability limitation
Camera evidence can support *apparent operability* only when observable cues exist, for example sustained local motion, visible indicator state, or task interaction. The system must not claim that a machine is mechanically or electrically healthy from CCTV evidence alone. Items that cannot be reliably verified visually are marked `OFFICER_VERIFICATION_REQUIRED`.

## Retention and access principles
A production deployment should apply role-based access, purpose limitation, data minimization, documented retention periods, audit logs, and secure deletion policies defined by MSDE/NSDC and applicable law. The SIH prototype demonstrates the technical privacy architecture; it must not be represented as completed legal-compliance certification.

## Prototype statement
The SIH prototype uses simulated scheme records and demonstration footage unless a source is explicitly identified. It demonstrates privacy-preserving compliance verification, not identification or profiling of real trainees.
