# Kaushal AI Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build one evidence-aware KaushalWatch assistant with multi-turn typed chat and a chained browser microphone-to-speaker workflow over real application data.

> **Provider migration note (2026-10-05):** The implementation now keeps the same single OpenAI Agents SDK agent and deterministic KaushalWatch tools, but uses Gemini 3.8 Flash through Google's OpenAI-compatible endpoint for chat/tool calling and Groq Whisper + Orpheus for voice. The OpenAI-specific model/key steps below are retained as historical implementation-plan context; current runtime configuration is documented in the README and `.env.example`.

**Architecture:** A single OpenAI Agents SDK agent calls read-only Python tools backed by the existing history, case, centre, evidence, and readiness services. A bounded in-memory conversation store preserves turns, while separate FastAPI transcription and speech endpoints use the same chat service and keep all credentials server-side.

**Tech Stack:** Python 3.10+, FastAPI, Pydantic 2, OpenAI Agents SDK, OpenAI Python client, Next.js 16, React 19, TypeScript, MediaRecorder, pytest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-05-kaushal-ai-assistant-design.md`

## Global Constraints

- Use exactly one agent named `Kaushal Assistant`; no handoffs, child agents, LangChain, CrewAI, AutoGen, Redis, or new database server.
- Operational claims must come from direct calls to existing Python stores/services, never HTTP calls back into FastAPI and never invented fallback data.
- Preserve anonymous attendance: never claim worker identity and describe vision results as detections or flags.
- Keep `OPENAI_API_KEY` backend-only; missing/disabled AI returns an assistant-specific 503 while monitoring remains available.
- Default models are `gpt-5-mini`, `gpt-transcribe`, and `gpt-4o-mini-tts`; all are configurable by the environment.
- Typed questions remain quiet; only voice-originated questions attempt autoplay, and every voice UI includes an AI-generated-voice disclosure.
- Do not persist uploaded recordings or generated speech; release browser microphone tracks and revoke object URLs.
- Preserve `/api/assistant/query`, all CV/OpenVINO paths, existing case/escalation policy, and surrounding dashboard layouts.
- The workspace currently has no `.git` metadata; replace each commit step with a status/diff inspection and report this limitation.

## Review Focus

- Concurrent requests using the same session ID must not corrupt or reorder a stored exchange; Task 2 includes a concurrency-safe store test.
- An audio upload with a misleading filename/MIME combination must be rejected or normalized to an allowed format before provider submission; Task 3 tests both extension and content-type validation.
- A tool must not retrieve an analysis or case belonging to another centre; Task 1 tests centre ownership enforcement.
- A component unmount while recording or playing must stop every track/audio element and revoke the object URL; Task 5 tests cleanup during navigation/unmount.
- A speech request must not accept arbitrary unbounded model output; Task 3 tests empty input and the configured character limit.

---

### Task 1: Deterministic operational tools and shared readiness service

**Files:**
- Create: `backend/app/services/runtime_readiness.py`
- Create: `backend/app/services/assistant_tools.py`
- Create: `backend/tests/test_assistant_tools.py`
- Modify: `backend/app/main.py`
- Modify: `backend/tests/test_runtime_readiness.py`

**Interfaces:**
- Consumes: `AnalysisHistoryStore`, `CaseStore`, `CentreSettingsStore`, `get_centre(...)`, existing detector/pipeline objects.
- Produces: `build_runtime_readiness(...) -> dict`, `AssistantDataContext`, `ToolResult`, and `KaushalToolset` methods named `get_centre_overview`, `get_runtime_readiness`, `get_operational_history`, `get_analysis_details`, `get_attendance_summary`, `get_practical_work_summary`, `get_escalations`, and `get_case_evidence`.

- [ ] **Step 1: Write failing readiness-sharing tests**

Add assertions that the route response and `KaushalToolset.get_runtime_readiness()` return the same detector authority/messages, and that no-data history returns explicit Asia/Kolkata bounds plus `available: false`.

- [ ] **Step 2: Run readiness/tool tests and verify the new imports fail**

Run: `pytest backend/tests/test_assistant_tools.py backend/tests/test_runtime_readiness.py -q`  
Expected: collection fails because `runtime_readiness` and `assistant_tools` do not exist.

- [ ] **Step 3: Implement shared readiness and the first four tool methods**

Create `build_runtime_readiness(attendance_detector, practical_detector, zones_path, evidence_path) -> dict`; replace the route body with this function; implement centre overview, readiness, operational-history period resolution, and centre-owned analysis lookup.

- [ ] **Step 4: Run focused tests and verify green**

Run: `pytest backend/tests/test_assistant_tools.py backend/tests/test_runtime_readiness.py -q`  
Expected: all current Task 1 tests pass.

- [ ] **Step 5: Write failing summary, escalation, ownership, and evidence tests**

Use temporary real stores to assert attendance/practical summaries preserve recorded details; escalation output uses existing policy; unknown named-worker data is marked unavailable; cross-centre analysis/case IDs are not returned; evidence output is compact and source records include only approved fields.

- [ ] **Step 6: Run the new tests and verify missing methods fail**

Run: `pytest backend/tests/test_assistant_tools.py -q`  
Expected: failures identify the four unimplemented tool methods or missing ownership behavior.

- [ ] **Step 7: Implement the remaining tool methods and sanitized provenance**

Each method returns `ToolResult(data: dict, sources: list[AssistantSource])`; period filtering converts stored UTC timestamps for Asia/Kolkata comparisons without modifying persisted data.

- [ ] **Step 8: Run Task 1 tests and existing product API tests**

Run: `pytest backend/tests/test_assistant_tools.py backend/tests/test_runtime_readiness.py backend/tests/test_product_experience_api.py -q`  
Expected: all pass and `/api/runtime-readiness` retains its existing contract.

- [ ] **Step 9: Inspect changes in lieu of commit**

Run: `git status --short` if metadata is restored; otherwise list Task 1 files and run `git diff --check` only when available.

---

### Task 2: Conversation store and single-agent application service

**Files:**
- Create: `backend/app/services/conversation_store.py`
- Create: `backend/app/services/assistant_service.py`
- Create: `backend/app/services/openai_assistant.py`
- Create: `backend/tests/test_assistant_service.py`
- Modify: `backend/app/models.py`
- Modify: `backend/requirements.txt`

**Interfaces:**
- Consumes: `KaushalToolset` and `ToolResult` from Task 1.
- Produces: `ConversationStore` protocol; `InMemoryConversationStore(max_sessions: int, max_turns: int, ttl_seconds: int)`; `AssistantProvider` protocol; `AssistantService.chat(message: str, session_id: str | None, centre_id: str) -> AssistantChatResponse`; `OpenAIAssistantProvider` implementing one Agents SDK agent.

- [ ] **Step 1: Write failing bounded-memory and concurrency tests**

Assert generated session IDs are opaque, turns remain ordered, the maximum turn count is enforced, expired sessions disappear, and concurrent appends preserve complete user/assistant exchanges.

- [ ] **Step 2: Run the store tests and verify RED**

Run: `pytest backend/tests/test_assistant_service.py -q`  
Expected: collection fails because `conversation_store` does not exist.

- [ ] **Step 3: Implement the conversation-store protocol and in-memory store**

Use a lock around bounded ordered dictionaries; expose `get_messages(session_id)`, `append_exchange(session_id, user_message, assistant_message)`, and `clear(session_id)`.

- [ ] **Step 4: Run store tests and verify green**

Run: `pytest backend/tests/test_assistant_service.py -q`  
Expected: all conversation-store tests pass while provider tests remain absent.

- [ ] **Step 5: Write failing assistant-service tests**

With a contract-faithful fake provider, assert text reaches the provider, tool-derived sources reach the response, a second turn includes first-turn context, empty/malformed output is rejected, provider/tool errors become `AssistantUnavailableError`, and no-data output remains explicit rather than fabricated.

- [ ] **Step 6: Run service tests and verify RED**

Run: `pytest backend/tests/test_assistant_service.py -q`  
Expected: failures identify missing `AssistantService` and response models.

- [ ] **Step 7: Implement response models and `AssistantService`**

Add Pydantic models for request/response/source/tool-call metadata to `models.py`; trim and length-limit input; call the provider with prior messages; append only completed exchanges.

- [ ] **Step 8: Run service tests and verify green**

Run: `pytest backend/tests/test_assistant_service.py -q`  
Expected: all application-service and conversation tests pass.

- [ ] **Step 9: Write failing OpenAI adapter contract tests**

Patch the Agents SDK runner boundary and assert one agent named `Kaushal Assistant` is configured with the eight Task 1 tools, operational instructions forbid invention/identity claims, tool results collect sanitized sources/timing, and model configuration defaults to `gpt-5-mini`.

- [ ] **Step 10: Implement `OpenAIAssistantProvider` and dependency**

Add the minimally pinned `openai-agents` package compatible with Python 3.10+; use `Agent`, `Runner`, `RunContextWrapper`, `function_tool`, and `ModelSettings` without handoffs; keep initialization lazy so missing keys do not break FastAPI startup.

- [ ] **Step 11: Run all Task 2 tests**

Run: `pytest backend/tests/test_assistant_service.py -q`  
Expected: all pass with no network calls.

- [ ] **Step 12: Inspect changes in lieu of commit**

Record the dependency and file list; do not create lock or cache artifacts outside the repository conventions.

---

### Task 3: FastAPI chat, transcription, and speech endpoints

**Files:**
- Create: `backend/app/services/voice_service.py`
- Create: `backend/tests/test_assistant_api.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/models.py`
- Modify: `backend/.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `AssistantService` and models from Task 2.
- Produces: `VoiceService.transcribe(filename: str, content_type: str, data: bytes) -> str`; `VoiceService.speech(text: str) -> bytes`; `POST /api/assistant/chat`; `POST /api/assistant/transcribe`; `POST /api/assistant/speech`.

- [ ] **Step 1: Write failing chat API tests**

Assert request validation, generated/preserved session IDs, centre-not-found, successful sources/tool metadata, disabled/missing-key 503 behavior, provider failure sanitization, and unchanged health/runtime routes.

- [ ] **Step 2: Run chat API tests and verify route absence**

Run: `pytest backend/tests/test_assistant_api.py -q`  
Expected: `/api/assistant/chat` returns 404.

- [ ] **Step 3: Implement lazy service factories and chat route**

Add `get_assistant_service()` with environment validation and injectable module globals for tests; use an async route and stable 422/503 error payloads; leave `/api/assistant/query` unchanged.

- [ ] **Step 4: Run chat API tests and verify green**

Run: `pytest backend/tests/test_assistant_api.py -q`  
Expected: chat tests pass.

- [ ] **Step 5: Write failing audio endpoint tests**

Assert allowed WebM/WAV/MP3 uploads reach a fake voice service; empty, oversized, unsupported, and misleading extension/MIME uploads fail before the provider; transcript text is returned; speech returns `audio/mpeg`; empty and over-limit text fail; provider errors return stable 503 responses.

- [ ] **Step 6: Run audio tests and verify route/service absence**

Run: `pytest backend/tests/test_assistant_api.py -q`  
Expected: audio route assertions fail with 404 or missing `VoiceService`.

- [ ] **Step 7: Implement `VoiceService` and audio routes**

Use the OpenAI client with `gpt-transcribe` and `gpt-4o-mini-tts`; validate at most 25 MB and the documented extensions/content types; use in-memory bytes only; return MP3 without writing generated files.

- [ ] **Step 8: Add configuration and ignore rules**

Document `OPENAI_API_KEY`, `KAUSHAL_AI_ENABLED`, `KAUSHAL_AI_MODEL`, `KAUSHAL_STT_MODEL`, `KAUSHAL_TTS_MODEL`, and `KAUSHAL_TTS_VOICE`; ignore temporary audio extensions only in designated runtime/temp directories rather than globally hiding user assets.

- [ ] **Step 9: Run Task 3 and existing API tests**

Run: `pytest backend/tests/test_assistant_api.py backend/tests/test_product_experience_api.py backend/tests/test_core.py -q`  
Expected: all pass with no external network calls.

- [ ] **Step 10: Inspect changes in lieu of commit**

Confirm no test recording, generated MP3, API key, or provider response artifact exists in the repository.

---

### Task 4: Frontend API contracts and typed chat rendering

**Files:**
- Modify: `web/app/lib/types.ts`
- Modify: `web/app/lib/api.ts`
- Modify: `web/app/components/AssistantPanel.tsx`
- Modify: `web/app/styles.css`
- Create: `web/e2e/assistant.spec.ts`

**Interfaces:**
- Consumes: Task 3 JSON contracts.
- Produces: `askAssistant(centreId, message, sessionId?)`, `transcribeAssistantAudio(blob)`, `synthesizeAssistantSpeech(text)`, typed `AssistantMessage`, `AssistantSource`, and `AssistantReply` UI contracts.

- [ ] **Step 1: Write a failing Playwright typed-chat test**

Intercept `/api/assistant/chat`; assert suggested questions render; typed submission sends `message`, `centre_id`, and a session ID; user and assistant messages accumulate; source links render; follow-up uses the returned session ID; New conversation clears messages and rotates the session.

- [ ] **Step 2: Run the focused browser test and verify RED**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: fails because the existing panel renders one reply and calls `/api/assistant/query`.

- [ ] **Step 3: Implement frontend API/types and typed multi-message panel**

Keep the panel location/size, add ready/configuration state, suggestions, scrolling transcript, source links, session state, and New conversation. Normalize assistant errors to the monitoring-safe message.

- [ ] **Step 4: Run the focused browser test and verify green**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: typed-chat scenario passes.

- [ ] **Step 5: Run TypeScript/build validation**

Run: `npm.cmd --prefix web run build`  
Expected: Next.js production build exits 0.

- [ ] **Step 6: Inspect changes in lieu of commit**

Confirm no new frontend AI dependency or browser-visible secret was added.

---

### Task 5: Browser microphone capture, chained voice request, and playback lifecycle

**Files:**
- Modify: `web/app/components/AssistantPanel.tsx`
- Modify: `web/app/styles.css`
- Modify: `web/e2e/assistant.spec.ts`

**Interfaces:**
- Consumes: `transcribeAssistantAudio`, `askAssistant`, and `synthesizeAssistantSpeech` from Task 4.
- Produces: microphone start/stop state, chained voice submission through the same chat method, autoplay/replay/stop controls, and complete media cleanup.

- [ ] **Step 1: Write failing MediaRecorder lifecycle tests**

Install browser-faithful test doubles before page load; assert microphone click requests permission once, shows “Listening…”, prevents a second recorder, Stop triggers transcription, every track is stopped, transcript reaches `/chat`, and the assistant response reaches `/speech`.

- [ ] **Step 2: Run voice tests and verify RED**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: microphone controls are absent.

- [ ] **Step 3: Implement recording and chained request state machine**

Prefer supported `audio/webm` variants then browser default; store one recorder/stream in refs; use one shared `submitMessage(text, voiceOrigin)` path; stop tracks in recorder stop/error/finally and component cleanup.

- [ ] **Step 4: Run recording tests and verify green**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: recording/chained-request tests pass.

- [ ] **Step 5: Write failing playback, error, and unmount tests**

Assert voice responses attempt autoplay; rejected `play()` exposes Play response; typed responses do not request speech; replay creates/uses the current audio URL; Stop pauses and resets playback; replacement/unmount revokes URLs and stops active media; permission denial, unsupported MediaRecorder, empty recording, transcription failure, speech failure, and backend timeout render clean errors while typed chat remains available.

- [ ] **Step 6: Run playback/error tests and verify RED**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: failures identify missing playback controls or cleanup.

- [ ] **Step 7: Implement audio playback and failure UX**

Use one `HTMLAudioElement`, cancel old playback before new audio, revoke obsolete URLs, expose replay/stop controls, add processing labels and the AI-generated-voice disclosure, and guard state updates after unmount.

- [ ] **Step 8: Run all assistant browser tests and production build**

Run: `npm.cmd --prefix web run test:e2e -- assistant.spec.ts --project=chromium`  
Expected: all assistant browser scenarios pass.  
Run: `npm.cmd --prefix web run build`  
Expected: build exits 0.

- [ ] **Step 9: Inspect changes in lieu of commit**

Confirm the component owns no live stream, audio URL, or generated file after test completion.

---

### Task 6: Documentation, full regression verification, and live-path attempt

**Files:**
- Modify: `README.md`
- Modify: `STATUS.md`
- Modify: `backend/.env.example`
- Modify: `web/.env.example` only if its existing API URL documentation needs clarification
- Modify: `docs/superpowers/specs/2026-10-05-kaushal-ai-assistant-design.md` status to implemented only after verification

**Interfaces:**
- Consumes: all preceding task contracts.
- Produces: setup/run/manual-test documentation and fresh verification evidence.

- [ ] **Step 1: Update setup and operational documentation**

Document backend dependency installation, environment variables without values, API/frontend start commands, typed chat steps, microphone/voice steps, AI disclosure, process-local memory, no-worker-identity limitation, missing-key behavior, and source/evidence navigation.

- [ ] **Step 2: Run repository hygiene checks**

Run: `rg -n "sk-[A-Za-z0-9]" . -g '!node_modules' -g '!*.md'` and `python scripts/check_repo_hygiene.py` when Python is available.  
Expected: no credentials, generated audio, runtime evidence, or forbidden artifacts are found.

- [ ] **Step 3: Run the complete backend suite**

Run from repository root: `pytest`  
Expected: zero failures. Record every pre-existing or environment failure by test name if the command cannot be made green.

- [ ] **Step 4: Run frontend production verification**

Run: `npm.cmd --prefix web run build`  
Expected: exit 0.  
Run the existing Playwright command with its documented video fixture plus `assistant.spec.ts`; expected: zero failures.

- [ ] **Step 5: Start backend and frontend for manual API/UI smoke tests**

Verify `/api/health`, a typed assistant request, missing-key isolation, the panel on a centre page, and browser recording/playback controls. Do not run video analysis from the assistant.

- [ ] **Step 6: Attempt the live OpenAI chained workflow only when configured**

If `OPENAI_API_KEY` exists, record and ask “What happened in the latest analysis?”, then follow with “What were the main discrepancies?” and “Which one should I investigate first?” Confirm transcription, the same session ID, tool metadata, grounded data/no-data wording, generated MP3, and browser playback. If no key exists, record this as not executable rather than substituting mocks.

- [ ] **Step 7: Perform final acceptance review**

Check every acceptance condition in the spec against a test result, inspected response, or documented limitation; keep the spec status as draft if required verification remains blocked.

- [ ] **Step 8: Final workspace inspection**

List all changed/new files, confirm no temp recordings or generated audio remain, and report that commits were impossible unless `.git` metadata has been restored.
