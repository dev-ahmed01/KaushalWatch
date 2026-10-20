'use client';

import { Mic, PauseCircle, Play, Send, Trash2, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { sendChatboxVoice, getChatboxVoice } from '../lib/api';

const LIMIT_MS = 60000;

export function VoiceNoteControls({ threadId, actorId, onSent }: {
  threadId: string; actorId: string; onSent: () => void;
}) {
  const recorderRef = useRef<MediaRecorder | null>(null);
  const tracksRef = useRef<MediaStream | null>(null);
  const startedRef = useRef(0);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const cancelRef = useRef(false);
  const [recording, setRecording] = useState(false);
  const [clip, setClip] = useState<Blob | null>(null);
  const [duration, setDuration] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  function cleanMedia() {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = null;
    tracksRef.current?.getTracks().forEach(track => track.stop());
    tracksRef.current = null;
  }
  function stop(cancel = false) {
    cancelRef.current = cancel;
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    cleanMedia();
    setRecording(false);
    if (cancel) { setClip(null); setDuration(0); }
  }
  useEffect(() => () => {
    cancelRef.current = true;
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    tracksRef.current?.getTracks().forEach(track => track.stop());
  }, []);
  useEffect(() => { setClip(null); setDuration(0); setError(''); }, [threadId, actorId]);

  async function start() {
    if (busy || recording || clip) return;
    setError('');
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError('Microphone recording is not supported in this browser.');
      return;
    }
    const format = ['audio/webm;codecs=opus', 'audio/webm', 'audio/ogg', 'audio/mp4'].find(t => MediaRecorder.isTypeSupported(t));
    if (!format) { setError('This browser has no supported voice-note format.'); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      tracksRef.current = stream;
      cancelRef.current = false;
      const chunks: BlobPart[] = [];
      const recorder = new MediaRecorder(stream, { mimeType: format });
      recorderRef.current = recorder;
      recorder.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      recorder.onerror = () => { setError('The recording device stopped unexpectedly.'); stop(true); };
      recorder.onstop = () => {
        cleanMedia();
        setRecording(false);
        if (cancelRef.current) return;
        const recorded = new Blob(chunks, { type: format.split(';')[0] });
        if (recorded.size < 16) { setError('No usable audio was recorded.'); return; }
        if (recorded.size > 4 * 1024 * 1024) { setError('Voice note is over the 4 MB limit.'); return; }
        setClip(recorded);
        setDuration(Math.max(100, Math.min(LIMIT_MS, Date.now() - startedRef.current)));
      };
      startedRef.current = Date.now();
      recorder.start(250);
      setRecording(true);
      timeoutRef.current = setTimeout(() => stop(), LIMIT_MS);
    } catch { cleanMedia(); setError('Microphone access was denied or unavailable.'); }
  }
  async function send() {
    if (!clip || busy) return;
    setBusy(true); setError('');
    try {
      await sendChatboxVoice(threadId, actorId, clip, duration, crypto.randomUUID());
      setClip(null); setDuration(0);
      onSent();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Voice note could not be saved');
    } finally { setBusy(false); }
  }

  return <div className="border-t border-[#e7edf5] bg-white px-3 py-2" aria-label="Voice note composer">
    <div className="flex flex-wrap items-center gap-2">
      {!clip && !recording && <button type="button" onClick={() => void start()} disabled={busy}
        aria-label="Record voice note" className="kw-focus flex items-center gap-1.5 rounded-lg border border-[#d7e5f6] px-3 py-2 text-[11px] font-semibold text-[#275fae]"><Mic size={15}/> Voice note</button>}
      {recording && <>
        <span role="status" className="text-[11px] font-semibold text-[#b42318]">Recording · max 60s</span>
        <button type="button" aria-label="Stop voice recording" onClick={() => stop()} className="kw-focus flex items-center gap-1 rounded-lg bg-[#2563eb] px-3 py-2 text-[11px] text-white"><PauseCircle size={15}/> Stop</button>
        <button type="button" aria-label="Discard voice recording" onClick={() => stop(true)} className="kw-focus rounded-lg p-2 text-[#667085]"><X size={15}/></button>
      </>}
      {clip && <>
        <span className="text-[11px] text-[#60738e]">Ready · {(duration/1000).toFixed(1)}s · {(clip.size/1024).toFixed(0)} KB</span>
        <button type="button" aria-label="Send voice note" disabled={busy} onClick={() => void send()}
          className="kw-focus inline-flex items-center gap-1.5 rounded-lg bg-[#2563eb] px-3 py-2 text-[11px] font-semibold text-white disabled:opacity-40"><Send size={14}/> Send audio</button>
        <button type="button" aria-label="Discard voice note" disabled={busy} onClick={() => {setClip(null);setDuration(0);}}
          className="kw-focus rounded-lg p-2 text-[#667085] disabled:opacity-40"><Trash2 size={15}/></button>
      </>}
      <span className="text-[10px] text-[#8494aa]">Voice is shared only after Send audio</span>
    </div>
    {error && <p role="alert" className="mt-1 text-[10px] text-[#b42318]">{error}</p>}
  </div>;
}

export function VoiceNotePlayer({ messageId, actorId, durationMs }: {
  messageId: string; actorId: string; durationMs: number | null;
}) {
  const [mediaUrl, setMediaUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => () => { if (mediaUrl) URL.revokeObjectURL(mediaUrl); }, [mediaUrl]);
  useEffect(() => { setMediaUrl(''); setError(''); }, [messageId, actorId]);
  async function load() {
    if (busy || mediaUrl) return;
    setBusy(true); setError('');
    try {
      const blob = await getChatboxVoice(messageId, actorId);
      setMediaUrl(URL.createObjectURL(blob));
    } catch { setError('Voice note unavailable or no longer authorised'); }
    finally { setBusy(false); }
  }
  return <div className="max-w-full" aria-label="Saved voice note">
    <p className="text-[11px] font-medium">Voice note {durationMs ? '· ' + Math.round(durationMs/1000) + 's' : ''}</p>
    {mediaUrl ? <audio controls preload="none" src={mediaUrl} className="mt-2 w-full max-w-[260px]" aria-label="Play verified voice note"/> :
      <button type="button" aria-label="Load voice note" disabled={busy} onClick={() => void load()}
        className="kw-focus mt-1 inline-flex items-center gap-1.5 rounded-lg border border-current px-2.5 py-1 text-[11px] disabled:opacity-50"><Play size={13}/>{busy ? 'Verifying…' : 'Load audio'}</button>}
    {error && <p role="alert" className="mt-1 text-[10px]">{error}</p>}
  </div>;
}
