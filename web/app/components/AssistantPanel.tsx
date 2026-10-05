'use client';

import Link from 'next/link';
import { FormEvent, useEffect, useRef, useState } from 'react';
import { askAssistant, getAssistantStatus, synthesizeAssistantSpeech, transcribeAssistantAudio } from '../lib/api';
import type { AssistantMessage, AssistantStatus } from '../lib/types';

const QUICK = [
  'What happened today?',
  'Any discrepancies?',
  "Show today's attendance.",
  'Summarise the latest analysis.',
];

type VoicePhase = 'idle' | 'recording' | 'transcribing' | 'asking' | 'speaking';

function sourceTime(value:string|null) {
  if (!value) return '';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
}

function friendlyMicrophoneError(error:unknown) {
  if (error instanceof DOMException && (error.name === 'NotAllowedError' || error.name === 'SecurityError')) {
    return 'Microphone permission was denied. Allow microphone access in your browser and try again.';
  }
  if (error instanceof DOMException && error.name === 'NotFoundError') {
    return 'No microphone was found on this device.';
  }
  return 'The microphone could not be started. Typed chat is still available.';
}

function isAbortError(error:unknown) {
  return error instanceof DOMException && error.name === 'AbortError';
}

export default function AssistantPanel({ centreId }:{centreId:string}) {
  const [question, setQuestion] = useState('');
  const [messages, setMessages] = useState<AssistantMessage[]>([]);
  const [sessionId, setSessionId] = useState<string>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [collapsed, setCollapsed] = useState(false);
  const [voicePhase, setVoicePhase] = useState<VoicePhase>('idle');
  const [playingMessageId, setPlayingMessageId] = useState<string>();
  const [speechLoadingId, setSpeechLoadingId] = useState<string>();
  const [autoplayBlockedId, setAutoplayBlockedId] = useState<string>();
  const [assistantStatus, setAssistantStatus] = useState<AssistantStatus|null>(null);
  const messageSequence = useRef(0);
  const mediaRecorderRef = useRef<MediaRecorder|null>(null);
  const mediaStreamRef = useRef<MediaStream|null>(null);
  const recordingChunksRef = useRef<Blob[]>([]);
  const startingRecordingRef = useRef(false);
  const recordingAttemptRef = useRef(0);
  const audioRef = useRef<HTMLAudioElement|null>(null);
  const audioUrlsRef = useRef(new Map<string, string>());
  const chatAbortRef = useRef<AbortController|null>(null);
  const transcriptionAbortRef = useRef<AbortController|null>(null);
  const speechAbortRef = useRef<AbortController|null>(null);
  const playbackRequestRef = useRef(0);
  const mountedRef = useRef(true);
  const centreRef = useRef(centreId);
  const conversationGenerationRef = useRef(0);

  function messageId() {
    messageSequence.current += 1;
    return `assistant-message-${messageSequence.current}`;
  }

  function releaseMicrophone() {
    mediaStreamRef.current?.getTracks().forEach(track => track.stop());
    mediaStreamRef.current = null;
  }

  function cancelRecording() {
    recordingAttemptRef.current += 1;
    const recorder = mediaRecorderRef.current;
    mediaRecorderRef.current = null;
    if (recorder) {
      recorder.ondataavailable = null;
      recorder.onstop = null;
      recorder.onerror = null;
      if (recorder.state !== 'inactive') recorder.stop();
    }
    recordingChunksRef.current = [];
    startingRecordingRef.current = false;
    releaseMicrophone();
    if (mountedRef.current) setVoicePhase('idle');
  }

  function stopPlayback() {
    playbackRequestRef.current += 1;
    speechAbortRef.current?.abort();
    speechAbortRef.current = null;
    const audio = audioRef.current;
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
      audioRef.current = null;
    }
    if (mountedRef.current) {
      setPlayingMessageId(undefined);
      setSpeechLoadingId(undefined);
    }
  }

  function revokeAudio() {
    stopPlayback();
    audioUrlsRef.current.forEach(url => URL.revokeObjectURL(url));
    audioUrlsRef.current.clear();
  }

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      chatAbortRef.current?.abort();
      transcriptionAbortRef.current?.abort();
      cancelRecording();
      revokeAudio();
    };
  }, []);

  useEffect(() => {
    let active = true;
    getAssistantStatus()
      .then(status => { if (active) setAssistantStatus(status); })
      .catch(() => {
        if (active) setAssistantStatus({ enabled: true, configured: true, available: false, voice_configured: false, voice_available: false });
      });
    return () => { active = false; };
  }, []);

  async function playResponse(id:string, text:string, autoplay=false) {
    stopPlayback();
    const request = playbackRequestRef.current;
    const generation = conversationGenerationRef.current;
    const controller = new AbortController();
    speechAbortRef.current = controller;
    setSpeechLoadingId(id);
    setAutoplayBlockedId(undefined);
    try {
      let url = audioUrlsRef.current.get(id);
      if (!url) {
        const speech = await synthesizeAssistantSpeech(text, controller.signal);
        if (!mountedRef.current || request !== playbackRequestRef.current || generation !== conversationGenerationRef.current) return;
        url = URL.createObjectURL(speech);
        audioUrlsRef.current.set(id, url);
      }
      if (request !== playbackRequestRef.current || generation !== conversationGenerationRef.current) return;
      const audio = new Audio(url);
      audioRef.current = audio;
      audio.onended = () => {
        if (audioRef.current === audio) audioRef.current = null;
        if (mountedRef.current) setPlayingMessageId(undefined);
      };
      await audio.play();
      if (!mountedRef.current || request !== playbackRequestRef.current || generation !== conversationGenerationRef.current) {
        audio.pause();
        return;
      }
      setPlayingMessageId(id);
    } catch (caught) {
      if (isAbortError(caught) || request !== playbackRequestRef.current || generation !== conversationGenerationRef.current) return;
      audioRef.current = null;
      setPlayingMessageId(undefined);
      if (autoplay && audioUrlsRef.current.has(id)) {
        setAutoplayBlockedId(id);
      } else {
        setError(caught instanceof Error ? caught.message : 'The spoken response could not be generated. The text response is still available.');
      }
    } finally {
      if (speechAbortRef.current === controller) speechAbortRef.current = null;
      if (mountedRef.current && request === playbackRequestRef.current && generation === conversationGenerationRef.current) {
        setSpeechLoadingId(undefined);
      }
    }
  }

  async function submitMessage(text:string, voiceOrigin=false, requiredGeneration=conversationGenerationRef.current) {
    const value = text.trim();
    if (!value || busy || assistantStatus?.available !== true || requiredGeneration !== conversationGenerationRef.current) return;
    const generation = requiredGeneration;
    chatAbortRef.current?.abort();
    const controller = new AbortController();
    chatAbortRef.current = controller;
    let speechStarted = false;
    setQuestion('');
    setError('');
    setMessages(current => [...current, { id: messageId(), role: 'user', text: value, voiceOrigin }]);
    setBusy(true);
    if (voiceOrigin) setVoicePhase('asking');
    try {
      const reply = await askAssistant(centreId, value, sessionId, controller.signal);
      if (!mountedRef.current || generation !== conversationGenerationRef.current) return;
      setSessionId(reply.session_id);
      const assistantMessageId = messageId();
      setMessages(current => [...current, {
        id: assistantMessageId,
        role: 'assistant',
        text: reply.message,
        sources: reply.sources,
        voiceOrigin,
      }]);
      if (voiceOrigin) {
        speechStarted = true;
        setVoicePhase('speaking');
        void playResponse(assistantMessageId, reply.message, true).finally(() => {
          if (mountedRef.current && generation === conversationGenerationRef.current) {
            setVoicePhase('idle');
          }
        });
      }
    } catch (caught) {
      if (!isAbortError(caught) && mountedRef.current && generation === conversationGenerationRef.current) {
        setError(caught instanceof Error ? caught.message : 'Kaushal Assistant is temporarily unavailable. Monitoring and analysis continue to work normally.');
      }
    } finally {
      if (chatAbortRef.current === controller) chatAbortRef.current = null;
      if (mountedRef.current && generation === conversationGenerationRef.current) {
        setBusy(false);
        if (voiceOrigin && !speechStarted) setVoicePhase('idle');
      }
    }
  }

  async function processRecording(blob:Blob, generation:number) {
    if (generation !== conversationGenerationRef.current) return;
    if (!blob.size) {
      setVoicePhase('idle');
      setError('No audio was captured. Please try recording again.');
      return;
    }
    transcriptionAbortRef.current?.abort();
    const controller = new AbortController();
    transcriptionAbortRef.current = controller;
    setVoicePhase('transcribing');
    setError('');
    try {
      const transcript = await transcribeAssistantAudio(blob, controller.signal);
      if (!mountedRef.current || generation !== conversationGenerationRef.current) return;
      if (!transcript.text.trim()) {
        setVoicePhase('idle');
        setError('No speech was detected. Please try again or type your question.');
        return;
      }
      await submitMessage(transcript.text, true, generation);
    } catch (caught) {
      if (!isAbortError(caught) && mountedRef.current && generation === conversationGenerationRef.current) {
        setVoicePhase('idle');
        setError(caught instanceof Error ? caught.message : 'Speech transcription failed. Typed chat is still available.');
      }
    } finally {
      if (transcriptionAbortRef.current === controller) transcriptionAbortRef.current = null;
    }
  }

  async function startRecording() {
    if (busy || assistantStatus?.voice_available !== true || voicePhase !== 'idle' || startingRecordingRef.current || mediaRecorderRef.current) return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Voice recording is not supported by this browser. Typed chat is still available.');
      return;
    }
    startingRecordingRef.current = true;
    const attempt = recordingAttemptRef.current + 1;
    recordingAttemptRef.current = attempt;
    const generation = conversationGenerationRef.current;
    setError('');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!mountedRef.current || attempt !== recordingAttemptRef.current) {
        stream.getTracks().forEach(track => track.stop());
        return;
      }
      mediaStreamRef.current = stream;
      const preferredTypes = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
      const mimeType = preferredTypes.find(type => MediaRecorder.isTypeSupported(type));
      if (!mimeType) {
        releaseMicrophone();
        setError('This browser does not provide a compatible audio recording format. Typed chat is still available.');
        return;
      }
      const recorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = recorder;
      recordingChunksRef.current = [];
      recorder.ondataavailable = event => {
        if (event.data.size) recordingChunksRef.current.push(event.data);
      };
      recorder.onerror = () => {
        recordingAttemptRef.current += 1;
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.onerror = null;
        recordingChunksRef.current = [];
        mediaRecorderRef.current = null;
        releaseMicrophone();
        if (mountedRef.current) {
          setVoicePhase('idle');
          setError('The recording failed. Please try again or type your question.');
        }
      };
      recorder.onstop = () => {
        const chunks = recordingChunksRef.current;
        recordingChunksRef.current = [];
        mediaRecorderRef.current = null;
        releaseMicrophone();
        const type = recorder.mimeType || mimeType || 'audio/webm';
        if (mountedRef.current) void processRecording(new Blob(chunks, { type }), generation);
      };
      recorder.start();
      setVoicePhase('recording');
    } catch (caught) {
      releaseMicrophone();
      if (mountedRef.current) setError(friendlyMicrophoneError(caught));
    } finally {
      startingRecordingRef.current = false;
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current;
    if (recorder?.state === 'recording') recorder.stop();
  }

  function newConversation() {
    conversationGenerationRef.current += 1;
    chatAbortRef.current?.abort();
    chatAbortRef.current = null;
    transcriptionAbortRef.current?.abort();
    transcriptionAbortRef.current = null;
    cancelRecording();
    revokeAudio();
    setBusy(false);
    setVoicePhase('idle');
    setMessages([]);
    setSessionId(undefined);
    setQuestion('');
    setError('');
    setAutoplayBlockedId(undefined);
  }

  useEffect(() => {
    if (centreRef.current === centreId) return;
    centreRef.current = centreId;
    newConversation();
  }, [centreId]);

  function collapseAssistant() {
    cancelRecording();
    stopPlayback();
    setCollapsed(true);
  }

  function submit(event:FormEvent) {
    event.preventDefault();
    void submitMessage(question);
  }

  const processing = voicePhase === 'transcribing' || voicePhase === 'asking' || voicePhase === 'speaking';
  const voiceInputBlocked = voicePhase === 'recording' || voicePhase === 'transcribing' || voicePhase === 'asking';
  const voiceAvailable = assistantStatus?.voice_available === true;
  const statusLabel = assistantStatus?.available
    ? 'Ready'
    : assistantStatus === null
      ? 'Checking'
      : assistantStatus.enabled && !assistantStatus.configured
        ? 'Setup required'
        : 'Unavailable';

  if (collapsed) return <aside className="neoAssistant collapsed">
    <button type="button" className="neoAssistantLauncher" onClick={() => setCollapsed(false)} aria-label="Ask Kaushal">
      <span>✦</span><b>Ask Kaushal</b>
    </button>
  </aside>;

  return <aside className="neoAssistant" aria-label="Kaushal Assistant">
    <div className="neoAssistantHead">
      <span className="neoAiOrb">✦</span>
      <div><b>Kaushal Assistant</b><small>Operational intelligence</small></div>
      <span className={`neoGrounded ${assistantStatus?.available ? '' : 'offline'}`}><i></i>{statusLabel}</span>
      <button type="button" className="neoAssistantClose" onClick={collapseAssistant} aria-label="Collapse assistant">×</button>
    </div>

    <div className="neoAssistantContext">
      <span>Current centre</span>
      <b>{centreId}</b>
      <small>Answers use recorded analyses, cases, evidence and policy state.</small>
    </div>

    <div className="neoAssistantToolbar">
      <button type="button" onClick={newConversation} disabled={messages.length === 0 && !busy && voicePhase === 'idle'}>New conversation</button>
    </div>

    {messages.length === 0 && <div className="neoAssistantQuick">
      {QUICK.map(item => <button key={item} type="button" onClick={() => void submitMessage(item)} disabled={busy || assistantStatus?.available !== true || voiceInputBlocked}>
        <span>○</span><b>{item}</b><i>›</i>
      </button>)}
    </div>}

    <div className="neoAssistantBody" aria-live="polite">
      {messages.length === 0 && !busy && !error && voicePhase === 'idle' && <div className="neoAiWelcome">
        <span>AI</span>
        <div>
          <b>Ask in plain language.</b>
          <p>I can explain recorded analyses, discrepancies, escalations, evidence and system readiness.</p>
        </div>
      </div>}

      {messages.map(message => <div className={`neoAssistantMessage ${message.role}`} key={message.id}>
        <div className={`neoChat ${message.role === 'assistant' ? 'ai' : 'user'}`}>{message.text}</div>
        {message.role === 'assistant' && <div className="neoAssistantAudio">
          {playingMessageId === message.id
            ? <button type="button" onClick={stopPlayback} aria-label="Stop response">■ Stop</button>
            : <button
                type="button"
                onClick={() => void playResponse(message.id, message.text)}
                disabled={speechLoadingId === message.id || !voiceAvailable}
                aria-label={autoplayBlockedId === message.id ? 'Play response' : audioUrlsRef.current.has(message.id) ? 'Replay response' : 'Play response'}
              >{speechLoadingId === message.id ? 'Preparing audio…' : autoplayBlockedId === message.id ? '🔊 Play response' : audioUrlsRef.current.has(message.id) ? '↻ Replay' : '🔊 Play response'}</button>}
          <small>AI-generated voice</small>
          {autoplayBlockedId === message.id && <em>Autoplay was blocked. Select Play response.</em>}
        </div>}
        {!!message.sources?.length && <div className="neoAssistantSources">
          <span>Sources</span>
          {message.sources.map(source => {
            const timestamp = sourceTime(source.timestamp);
            return <Link href={source.href} key={`${source.kind}-${source.id}`}>
              <b>{source.label}</b>
              <small>{source.id}{timestamp ? ` · ${timestamp}` : ''}</small>
            </Link>;
          })}
        </div>}
      </div>)}
      {busy && <div className="neoAssistantThinking">
        <div className="neoChat ai loading"><i></i><i></i><i></i></div>
        <span>{voicePhase === 'speaking' ? 'Preparing spoken response…' : 'Reviewing KaushalWatch data…'}</span>
      </div>}
      {error && <div className="neoAssistantError" role="alert">{error}</div>}
      {assistantStatus && !assistantStatus.available && <div className="neoAssistantConfig" role="status">
        {assistantStatus.enabled && !assistantStatus.configured
          ? 'Kaushal Assistant requires a Gemini API key on the backend. Monitoring and analysis continue normally.'
          : 'Kaushal Assistant is unavailable. Monitoring and analysis continue normally.'}
      </div>}
      {assistantStatus?.available && !voiceAvailable && <div className="neoAssistantConfig" role="status">
        Voice requires a Groq API key. Typed chat remains available.
      </div>}
    </div>

    {voicePhase === 'recording' && <div className="neoVoiceStatus" role="status">
      <span><i></i>Listening...</span>
      <button type="button" onClick={stopRecording} aria-label="Stop recording">Stop</button>
    </div>}
    {voicePhase === 'transcribing' && <div className="neoVoiceStatus processing" role="status">Understanding your question...</div>}

    <form className="neoAssistantComposer" onSubmit={submit}>
      <input
        value={question}
        onChange={event => setQuestion(event.target.value)}
        placeholder="Ask Kaushal anything..."
        aria-label="Message Kaushal Assistant"
        disabled={busy || assistantStatus?.available !== true || voiceInputBlocked}
      />
      <button
        className="neoMicButton"
        disabled={busy || !voiceAvailable || processing || voicePhase === 'recording'}
        type="button"
        onClick={() => void startRecording()}
        aria-label="Start voice question"
      >🎤</button>
      <button className="neoSendButton" disabled={busy || assistantStatus?.available !== true || voiceInputBlocked || !question.trim()} type="submit" aria-label="Send message">↑</button>
    </form>
  </aside>;
}
