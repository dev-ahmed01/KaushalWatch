# Kaushal AI Assistant Design

**Date:** 2026-10-05  
**Status:** Implemented; live free-provider smoke test pending  
**Scope:** One grounded KaushalWatch assistant with text chat and chained voice interaction

## Purpose

Kaushal Assistant gives supervisors and administrators a concise conversational view of KaushalWatch operational results. It answers from persisted analyses, compliance cases, escalation policy, evidence metadata, and runtime-readiness state. It does not infer facts that KaushalWatch has not recorded, identify anonymous workers, or run expensive computer-vision analysis during a chat request.

Success means the existing assistant panel supports multi-turn typed and voice conversations through the same backend agent; operational answers are produced from deterministic tools over existing Python services; evidence-aware sources are returned to the UI; failures remain isolated from monitoring; and missing data or AI configuration is stated plainly.

## Existing System Boundaries

The FastAPI application in `backend/app/main.py` owns file-backed stores for:

- `data/analysis_history.json` through `AnalysisHistoryStore`;
- `data/cases.json` through `CaseStore`;
- evidence records embedded in `ComplianceCase` objects and served from `/evidence`;
- centre metadata and calculated escalation state through `demo_network.py`;
- runtime-readiness state assembled from the existing attendance, practical-work, infrastructure, and evidence services.

The existing `web/app/components/AssistantPanel.tsx` is already embedded throughout centre, verification, review, reports, escalations, history, and settings pages. The current `/api/assistant/query` endpoint is deterministic and keyword-based. It remains available for compatibility but is not presented as the new AI service.

KaushalWatch deliberately tracks anonymous occupancy rather than named individuals. The assistant may report recorded aggregate worker counts and temporary track observations, but must say that worker identity is unavailable when asked about a named worker.

## Architecture

The implementation uses one OpenAI Agents SDK `Agent` named **Kaushal Assistant**. It has no handoffs or child agents. The SDK manages the model/tool loop; all KaushalWatch tool execution remains local to the FastAPI process.

```text
AssistantPanel
  -> POST /api/assistant/chat
  -> AssistantService
  -> OpenAI Agents SDK Runner
  -> Gemini 3.8 Flash via Google's OpenAI-compatible endpoint
  -> deterministic KaushalWatch function tool
  -> existing store/service/data
  -> concise grounded answer + sanitized sources
```

Three focused backend units provide replaceable boundaries without an elaborate provider framework:

1. `AssistantService` creates and runs the single agent, manages the conversation input, and returns an application response.
2. `ConversationStore` retains a bounded number of recent user/assistant turns per opaque session ID. V1 uses an in-memory implementation with expiration and maximum-turn limits.
3. `VoiceService` wraps Groq Whisper transcription and Orpheus speech generation through Groq's OpenAI-compatible API. Tests replace this external boundary with a fake; production never returns fabricated transcripts or audio.

The application injects existing stores, centre lookup, and a readiness provider into a per-run tool context. Tools do not import or call FastAPI routes and never make HTTP requests to the same backend.

## Model and Provider Configuration

The default text model is `gemini-3.8-flash`, configurable with `KAUSHAL_AI_MODEL`, and is called through Google's OpenAI-compatible endpoint. Recorded speech uses Groq `whisper-large-v3-turbo`, configurable with `KAUSHAL_STT_MODEL`. Speech output uses Groq `canopylabs/orpheus-v1-english`, configurable with `KAUSHAL_TTS_MODEL`, and the `hannah` voice by default, configurable with `KAUSHAL_TTS_VOICE`. Orpheus accepts at most 200 input characters, so the full answer stays on screen while speech uses a bounded excerpt.

`GEMINI_API_KEY` and `GROQ_API_KEY` remain backend-only. `KAUSHAL_AI_ENABLED` defaults to `true`. Gemini configuration controls typed chat; Groq configuration controls voice independently, so missing Groq credentials do not disable typed chat. When Gemini is disabled or unconfigured, assistant chat returns a specific service-unavailable response while all non-assistant routes continue normally. The browser receives neither key.

## Agent Instructions and Trust Rules

The agent is an operational intelligence assistant for KaushalWatch. Its instructions require it to:

- use a tool before stating any centre-specific operational fact;
- distinguish recorded observations, system conclusions, and unavailable information;
- describe vision-derived claims as detections or flags rather than certainty;
- respect stored detector authority, confidence, camera-trust, status, severity, and escalation results;
- never calculate a replacement escalation severity in the model;
- never invent people, identities, metrics, events, evidence, analyses, or dates;
- explain that current attendance data is anonymous when identity is requested;
- state plainly when a requested period has no data;
- keep answers concise unless the user asks for detail;
- recommend human review for consequential workplace-monitoring decisions.

The agent receives the current server date and `Asia/Kolkata` timezone in its run context. Relative periods are resolved deterministically before store filtering, and tool output includes explicit ISO dates.

## Deterministic Tools

All tools are read-only.

### `get_centre_overview`

Returns the existing calculated centre state: centre ID/name, batch, aggregate verification pillar states, analysis count, pending/confirmed case counts, current escalation label/reasons/next action, and last-analysis timestamp.

### `get_runtime_readiness`

Returns the existing attendance, practical-work, infrastructure, and evidence readiness results, including detector authority and explanatory messages. Readiness assembly is moved behind a reusable service function so the API route and tool share the same logic.

### `get_operational_history`

Accepts one of `today`, `yesterday`, `this_week`, `last_week`, `last_7_days`, `last_30_days`, or an explicit start/end date plus an optional analysis type. It returns matching analysis rows newest-first, summary counts, explicit period bounds, and a no-data marker.

### `get_analysis_details`

Accepts an analysis ID and returns that persisted row only when it belongs to the selected centre. It includes the recorded summary, outcome, analysis type, timestamp, and compact details.

### `get_attendance_summary`

Returns attendance analyses for the resolved period, recorded reported/estimated occupancy and discrepancy values when present, relevant attendance cases, and an explicit note that no worker identity is retained.

### `get_practical_work_summary`

Returns practical-work analyses and cases for the resolved period, including stored activity/zone metrics and authorization status when present. It preserves the existing limitation that visual motion is a proxy and not proof of task quality.

### `get_escalations`

Returns persisted cases filtered by status/severity when requested, plus the centre's escalation result calculated by existing policy. It includes unresolved, under-review, virtual-verification, confirmed, resolved, and false-positive states without redefining their severity.

### `get_case_evidence`

Accepts a case ID and returns compact case details, decision/review history, evidence IDs, timestamps, integrity/duplicate markers, camera metadata when present, and links to the existing review/evidence UI. It never returns image bytes or large raw JSON to the model.

## Provenance

Each tool appends sanitized source records to the run context. The chat response de-duplicates these records and returns only sources used during that turn.

A source contains:

```json
{
  "kind": "analysis | case | evidence | readiness | centre",
  "id": "AN-000001",
  "label": "Attendance analysis",
  "timestamp": "2026-10-05T09:00:00+00:00",
  "href": "/centres/DEMO-KA-104/history"
}
```

Tool metadata exposed to the browser is limited to tool name, success/failure, and duration. Arguments, model reasoning, hidden prompts, raw provider responses, and chain-of-thought are not returned.

## Conversation Memory

The chat request accepts an optional `session_id`. The backend generates a cryptographically opaque ID when absent. The in-memory store keeps a bounded recent history for each session and expires idle sessions. It is concurrency-safe within one process and exposes an interface that can later be backed by durable storage.

The service sends previous user and assistant messages with the new message so follow-ups such as “Which one was most serious?” retain context. Tool results are re-fetched when the follow-up needs current operational facts. A “New conversation” action creates a new session ID and clears the local transcript without mutating KaushalWatch data.

V1 memory is process-local: restarting the API or using multiple uncoordinated workers loses conversation history. This limitation is documented.

## HTTP API

### `POST /api/assistant/chat`

Request:

```json
{
  "message": "What happened today?",
  "session_id": "optional opaque ID",
  "centre_id": "DEMO-KA-104"
}
```

Response:

```json
{
  "message": "There are no recorded analyses for 2026-10-05.",
  "session_id": "opaque ID",
  "sources": [],
  "tool_calls": [
    {"name": "get_operational_history", "status": "success", "duration_ms": 3}
  ]
}
```

Messages are trimmed and length-limited. Centre IDs must exist. Provider or tool failures return a stable assistant-specific error without leaking internal exception text.

### `POST /api/assistant/transcribe`

Accepts multipart `audio`. The endpoint validates non-empty content, a 25 MB maximum, and browser-compatible recorded types (`webm`, `wav`, `mp3`, `mp4`, `mpeg`, `mpga`, and `m4a`). It returns `{ "text": "..." }`. Empty/unsupported uploads receive 4xx responses; provider failures receive a stable 503 response.

### `POST /api/assistant/speech`

Accepts `{ "text": "..." }`, applies a conservative text-length limit, and returns non-cacheable `audio/wav` bytes. `VoiceService` sends a whitespace-normalized excerpt of at most 200 characters to Orpheus while the full text remains in the UI. Provider failures receive a stable 503 response.

The frontend composes these three endpoints instead of using a separate voice agent.

## Voice Flow

```text
microphone permission
  -> MediaRecorder (preferred supported browser MIME type)
  -> user stops recording
  -> all microphone tracks stop
  -> POST /api/assistant/transcribe
  -> transcript displayed as the user message
  -> POST /api/assistant/chat with the same session ID
  -> the single Kaushal Assistant and its tools
  -> assistant text displayed with sources
  -> POST /api/assistant/speech
  -> MP3 object URL
  -> autoplay after voice-originated requests when permitted
  -> replay or stop controls
```

The UI never starts a second recorder while one is active. It selects a supported MIME type with `MediaRecorder.isTypeSupported`, handles permission denial and missing APIs, rejects empty recordings, stops every stream track after stop/error/unmount, cancels active playback before replacing it, and revokes obsolete object URLs.

If autoplay is blocked, the response remains visible and the play control is emphasized. Typed questions never autoplay. The panel states unobtrusively that spoken responses use an AI-generated voice.

## Assistant Panel UX

The existing side panel remains in place and receives only focused changes:

- header: “Kaushal Assistant” and configuration/ready state;
- scrollable user/assistant message history;
- suggested questions when empty;
- structured source links beneath the relevant assistant response;
- composer with text input, microphone, and Send;
- visible “Listening…”, Stop, “Understanding your question…”, and response-generation states;
- replay/stop speech controls on assistant messages;
- New conversation action;
- concise inline errors that explain monitoring continues normally.

Keyboard submission and typed chat remain available in every voice state except during the short request currently being sent. The interface does not add a waveform or redesign surrounding dashboard pages.

## Failure Handling

- Missing/disabled AI configuration: return 503 and show “Kaushal Assistant requires AI configuration. Monitoring and analysis continue to work normally.”
- Model/provider timeout or outage: return 503 and show the standard temporary-unavailability message.
- Store/database read failure or tool exception: log the tool name and error server-side, mark the tool call failed, and have the assistant state that the requested data could not be retrieved; do not substitute invented data.
- No matching report, analysis, case, or evidence: return a successful empty tool result and say the information is unavailable.
- Transcription/speech failure: keep the text workflow usable and show a voice-specific retry message.
- Permission denial, missing MediaRecorder, unsupported MIME, or empty audio: remain in the panel and release any acquired stream.
- Malformed provider result: reject it as an assistant service error rather than rendering it.

Logs contain request/session correlation IDs, tool names and durations, agent completion, transcription completion, speech completion, and sanitized errors. Logs exclude API keys, raw audio, hidden prompts/reasoning, and unnecessary transcript content.

## Testing Strategy

Implementation follows red-green-refactor cycles.

Backend unit/integration tests use temporary real `AnalysisHistoryStore` and `CaseStore` instances. External Gemini/Groq provider boundaries are replaced with contract-faithful fakes only in tests. Tests cover:

- operational tool retrieval from real temporary records;
- explicit empty-data results and anonymous-worker limitations;
- tool failures without hallucinated fallback;
- chat request/response and sanitized provenance;
- stable session IDs and a context-dependent second turn;
- missing key/disabled configuration;
- supported, empty, oversized, and unsupported audio uploads;
- transcription feeding the same `AssistantService` used by typed chat;
- speech bytes and media type;
- provider transcription, speech, and agent failures.

Playwright tests intercept only the external assistant HTTP boundary and provide browser-faithful `getUserMedia`, `MediaRecorder`, and audio playback doubles. They verify typed submission, recording, stop, loading labels, transcript/response rendering, automatic speech request for voice input, autoplay fallback, replay/stop, track release, and unmount cleanup.

Verification commands are the complete backend pytest suite, frontend TypeScript/build, existing Playwright suite, and new assistant browser tests. If a Python runtime and the appropriate `GEMINI_API_KEY` / `GROQ_API_KEY` values are available, a manual live chained test asks:

1. “What happened in the latest analysis?”
2. “What were the main discrepancies?”
3. “Which one should I investigate first?”

Without the provider keys, provider-dependent production behavior is not replaced by mocks; the live test is reported as unavailable while automated contract tests still exercise the complete application pipeline.

## Dependency and Documentation Changes

The backend keeps the minimal supported OpenAI Agents SDK dependency, which includes the OpenAI Python client used as the OpenAI-compatible transport for Gemini and Groq. No LangChain, CrewAI, AutoGen, Redis, database server, or frontend AI SDK is introduced.

`backend/.env.example` documents the feature flag and model/voice variables without credentials. `README.md` documents setup, endpoint purpose, local run commands, manual text/voice checks, session-memory limitations, and the privacy/AI-voice disclosures. `.gitignore` continues excluding secrets and generated runtime/audio data; the implementation does not persist uploaded recordings or generated speech.

## Out of Scope

- Worker identity lookup or facial recognition.
- Triggering synchronous video analysis from chat.
- Realtime speech-to-speech or WebSocket voice transport.
- Durable or distributed conversation storage.
- Multiple agents, handoffs, autonomous actions, or case-status mutation.
- Replacing existing CV, OpenVINO, escalation, evidence, or review logic.

## Acceptance Conditions

The change is complete only when the existing panel provides typed multi-turn chat and a working chained microphone-to-speaker flow; operational claims use direct tools over persisted KaushalWatch data; unavailable identity/data is qualified; source links are structured; microphone and playback resources are cleaned up; failures do not affect monitoring; credentials remain server-side; existing APIs and CV behavior remain intact; backend tests pass; and the frontend production build and browser tests pass.
