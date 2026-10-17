# Phase 3Q — Numeric Continuity Counterfactuals

**OFFLINE RESEARCH ONLY.** Based on completed Phase 3P Day 3 / Day 4
development JSON. No video reads, decoder calls, media exports, source
reference changes, operational incident status, or scene-cue suppression.

## Real development evidence motivating this phase

- 28 windows in all: Day 3 + Day 4 each have six defocus, six moved,
  and two qualifying annotated-normal controls.
- Four of eight predeclared normal-control candidates were SKIPPED
  due to non-normal labels. Four controls are not representative of
  full-day normal footage or enough to estimate officer burden.
- 2,548 numeric samples were recorded: 1,274 per day.
- Phase3P reported 1,728 valid paired observations in total.
- Another 400 non-warmup observations had numerically usable sharpness
  despite missing combined feature ratios (184 Day 3, 216 Day 4).
  The upstream paired feature gate demanded positive edge as well.
- 420 first-window samples (15 per window) have no 30-second history.
  Neither warmup nor unknown evidence is healthy or recovered footage.
- Exploratory Phase3P sharpness-decline <= 0.5 appeared inside all
  twelve selected defocus windows, first signal offsets 0–12 s.
- The same cue appeared during one of twelve selected moved events
  and in one of the four qualifying normal-control windows.
- Signals also occur during normal-labeled portions surrounding events;
  they are not automatically false alarms without visual adjudication.

## Implemented counterfactuals

Script: scripts/analyze_phase3q_numeric_continuity.py

1. phase3p_original_unmodified: exactly the original reported Boolean
   for each sample with available Phase3P paired ratio.
2. sharpness_only_numeric: reconstructs the 30-second past-to-current
   sharpness ratio from two existing frozen-reference-relative samples,
   without requiring an edge denominator to be nonzero.
3. sharpness_2_of_previous_3: an exploratory 2-of-3 recent ratio rule.
4. sharpness_3_consecutive: an exploratory 3-in-a-row ratio rule.

All rules use a previously inspected development cutoff of 0.5, and
therefore are NOT preregistered or validated classification policies.
Only causal numeric history enters the candidate rule. Source annotations
are applied afterward to summarize target, normal and preexisting-warning
states, explicitly distinguishing candidate episode onset from an
already-active candidate at annotated event start.

## Preliminary descriptive trade-off on the uploaded JSON

| Research diagnostic | Defocus windows with cue | Moved windows with cue in moved interval | Qualifying normal controls with cue | First defocus cue offset range |
| --- | ---: | ---: | ---: | --- |
| Original >=1 sample | 12/12 | 1/12 | 1/4 | 0–12s |
| Paired sharpness only | 12/12 | 1/12 | 1/4 | 0–12s |
| Paired sharpness, 2 of 3 | 12/12 | 1/12 | 1/4 | 2–14s |
| Paired sharpness, 3 consecutive | 12/12 | 1/12 | 0/4 | 4–16s |

These are exploration of KNOWN development intervals, not sensitivity,
specificity, precision, independent camera validation or field latency.
Strict confirmation reduces short isolated numeric spikes in this tiny
normal sample, but does NOT remove event-adjacent normal cues and does
NOT resolve ambiguous legitimate movement. Do not select or deploy a
confirmation policy on these already inspected records.

## Run using only existing Phase3P numeric evidence

From a fresh checkout of experiment/phase3q-numeric-continuity-counterfactuals:

    python scripts/analyze_phase3q_numeric_continuity.py --input path/to/causal-20261018-031422.json --out path/to/phase3q-new.json

Output is a new numeric JSON file, no images/video, all candidate policies
and event-window summaries preserved without mutating the original.
Source is validated for two days, unqualified flags, event denominators,
finite measurements, missing-data states and original ratio consistency.
Unknown-low-texture or discontinuous history cannot be silently rescued
by the sharpness-only analysis; such cases remain abstained.

## Next scientific gate

1. Before any larger detector replay, use bounded, systematic NORMAL
   controls across the entire day including night, illumination shifts,
   low texture, post-event carryover and varied natural movement.
2. Keep annotated-normal distinct from independently verified usable
   camera evidence. Blindly label additional camera/site footage.
3. Preserve raw scene-review cues; no suppression or automatic incident
   closure or reference re-enrollment is authorized.
4. Freeze candidate parameters and pre-register independent camera
   acceptance, including missed defocus/covered/moved incidents,
   normal-hour warning episodes, onset delays, UNKNOWN and persistence.
5. Require source provenance, private storage/IAM and officer audits
   before considering any production integration.

All stacked experimental PRs remain draft, unmerged to production main.
