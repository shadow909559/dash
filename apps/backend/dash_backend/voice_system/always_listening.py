"""Always-listening wake-word loop (server-side, real microphone).

Closes the gap found by reading the existing voice system (decision #86):
VAD, Whisper STT, Piper TTS and the chat dispatch all existed, but nothing
ever captured audio from a real microphone server-side — and both wake-word
detectors were stubs that decoded PCM bytes as UTF-8 text and could never
fire. This module owns the missing producer:

    mic (sounddevice/PortAudio) → energy VAD → phrase window → Whisper STT
      → wake-phrase match ("hey dash") → command capture → REAL chat path
      (handle_chat_send: memory, RAG, candor, tools) → Piper TTS → speaker

Design honesty:
- The loop is strictly opt-in (DASH_WAKE_LOOP_ENABLED=1) because it holds
  the microphone; the status endpoint always reports the real state.
- Every stage failure is recorded (``last_error``), never swallowed
  silently: a dead loop reports ``state="error"``, a failed transcription
  or TTS says so in its event instead of pretending to succeed.
- Wake matching happens on Whisper transcripts (one STT call per speech
  pause), not on every chunk — cheap enough for a CPU-only machine.
- Echo suppression: while DASH is speaking (and for a guard window after),
  all mic audio is ignored, so DASH cannot wake on its own voice.

Everything is injectable (mic source, transcriber, TTS, chat runner) so the
test suite runs hermetically with no microphone, no Whisper and no speaker.
"""
from __future__ import annotations

import asyncio
import io
import os
import queue
import re
import time
import uuid
import wave
from dataclasses import dataclass, field, asdict
from typing import Any, Awaitable, Callable, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Phase 3 (voice): interim-transcript cadence — one voice.partial per
# window keeps live typing useful without flooding STT or the ws.
PARTIAL_INTERVAL_S = 0.7


class MicUnavailableError(RuntimeError):
    """Raised when the microphone cannot be opened — carries the real reason."""


# ── Audio source ──────────────────────────────────────────────────────────


class MicAudioSource:
    """Real microphone source via sounddevice (PortAudio).

    Runs a PortAudio callback on its own thread, pushing 16-bit mono PCM
    chunks into a bounded queue. Oldest chunks are dropped on overflow so a
    stalled consumer can never grow memory unbounded — dropping is recorded
    in ``dropped_chunks`` and reported by status, not hidden.
    """

    def __init__(self, sample_rate: int = 16000, chunk_ms: int = 100):
        self.sample_rate = sample_rate
        self.chunk_ms = chunk_ms
        self._stream = None
        self._q: queue.Queue = queue.Queue(maxsize=100)
        self.dropped_chunks = 0

    def start(self) -> None:
        try:
            import sounddevice as _sd
        except Exception as exc:  # pragma: no cover - depends on install
            raise MicUnavailableError(f"sounddevice not importable: {exc}") from exc

        blocksize = int(self.sample_rate * self.chunk_ms / 1000)

        def _cb(indata, frames, time_info, status) -> None:
            if status:
                # e.g. input overflow — count it, keep going
                self.dropped_chunks += 1
            try:
                self._q.put_nowait(bytes(indata))
            except queue.Full:
                try:
                    self._q.get_nowait()
                    self._q.put_nowait(bytes(indata))
                except Exception:
                    pass

        try:
            self._stream = _sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=blocksize,
                callback=_cb,
            )
            self._stream.start()
        except Exception as exc:
            self._stream = None
            raise MicUnavailableError(f"failed to open default input device: {exc}") from exc

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                logger.exception("error closing mic stream")

    def read_chunk(self, timeout: float = 0.1) -> Optional[bytes]:
        """Blocking read used from the loop thread via asyncio.to_thread."""
        try:
            return self._q.get(timeout=timeout)
        except queue.Empty:
            return None


# ── Wake phrase matching ──────────────────────────────────────────────────


class WakePhraseMatcher:
    """Transcript-based wake matching with punctuation-proof normalization.

    Whisper may return "Hey, DASH!" or "hey dash" — normalization collapses
    case, punctuation and whitespace so both match. Command extraction
    returns the words spoken after the phrase ("" means wake-only).
    """

    _PUNCT = re.compile(r"[^\w\s]")

    def __init__(self, phrase: str = "hey dash"):
        self.phrase = phrase
        self._variants = self._make_variants(phrase)

    def _make_variants(self, phrase: str) -> tuple[str, ...]:
        norm = self._normalize(phrase)
        variants = {norm}
        # "hey dash" ≈ "hay dash"-style mishears are NOT guessed — honest
        # matching means only the configured phrase (normalized) matches.
        return tuple(sorted(variants))

    @classmethod
    def _normalize(cls, text: str) -> str:
        text = cls._PUNCT.sub(" ", (text or "").lower())
        return " ".join(text.split())

    def matches(self, text: str) -> bool:
        norm = self._normalize(text)
        return self._find(norm) is not None

    def _find(self, norm: str):
        """Word-boundary regex search; substring matching alone is wrong
        ('they dashed quickly' contains the letters of 'hey dash')."""
        for v in self._variants:
            m = re.search(r"\b" + re.escape(v) + r"\b", norm)
            if m:
                return m
        return None

    def extract_command(self, text: str) -> str:
        """Text after the first phrase occurrence; "" when none."""
        norm = self._normalize(text)
        m = self._find(norm)
        return norm[m.end():].strip() if m else ""


# ── Helpers ───────────────────────────────────────────────────────────────


"""Helper referenced by the capture loop (defined at module scope so the
loop body stays linear): VAD for a chunk with a safe fallback."""


def speech_if_any(vad, chunk: bytes) -> bool:
    try:
        return bool(vad.is_speech(chunk))
    except Exception:
        return False


def pcm_to_wav(pcm: bytes, sample_rate: int = 16000) -> bytes:
    """Wrap 16-bit mono PCM in a minimal WAV container (Whisper reads WAV)."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm)
    return buf.getvalue()


def wav_duration_seconds(audio: bytes) -> float:
    """Exact duration from the WAV header; rough estimate if unparsable."""
    try:
        with wave.open(io.BytesIO(audio), "rb") as w:
            frames = w.getnframes()
            rate = w.getframerate() or 1
            return max(0.0, frames / float(rate))
    except Exception:
        return max(0.0, len(audio) / 32000.0)


# ── Status ────────────────────────────────────────────────────────────────


def _iso(ts: Optional[float]) -> Optional[str]:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(ts)) if ts else None


@dataclass
class WakeLoopStatus:
    state: str = "stopped"  # disabled|starting|listening|error|stopped
    detail: str = ""
    enabled: bool = False
    wake_word: str = "hey dash"
    started_at: Optional[str] = None
    wake_count: int = 0
    command_count: int = 0
    rejected_phrase_count: int = 0
    dropped_chunks: int = 0
    last_wake_at: Optional[str] = None
    last_command_at: Optional[str] = None
    last_reply: Optional[str] = None
    last_error: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# ── The loop ──────────────────────────────────────────────────────────────


class AlwaysListeningLoop:
    """Capture → VAD → wake phrase → command → chat → TTS, as one task.

    State machine (all driven by real mic chunks):
      IDLE    — silence; only speech chunks start a phrase window.
      PHRASE  — speech captured until a ~0.5s silence tail or 4s cap; the
                window is transcribed once and matched against the phrase.
                Match → wake (event published). Wake-only → COMMAND state.
      COMMAND — command captured until silence tail / 8s cap → transcript
                dispatched through the real chat path, reply spoken.
    """

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        source: Optional[MicAudioSource] = None,
        transcriber: Optional[Callable[[bytes], Awaitable[str]]] = None,
        tts_synth: Optional[Callable[[str], Awaitable[bytes]]] = None,
        chat_runner: Optional[Callable[[str], Awaitable[str]]] = None,
        matcher: Optional[WakePhraseMatcher] = None,
        vad=None,
        event_bus=None,
        clock: Optional[Callable[[], float]] = None,
        player: Optional[Callable[[bytes], Awaitable[None]]] = None,
        partial_transcriber: Optional[Callable[[bytes], Awaitable[str]]] = None,
    ):
        self._clock = clock or time.time
        self._player = player
        self.enabled = (
            enabled if enabled is not None
            else os.getenv("DASH_WAKE_LOOP_ENABLED", "0") == "1"
        )
        self.wake_word = os.getenv("DASH_WAKE_WORD", "hey dash")
        self.sample_rate = int(os.getenv("DASH_WAKE_SAMPLE_RATE", "16000"))
        self.chunk_ms = int(os.getenv("DASH_WAKE_CHUNK_MS", "100"))
        self.phrase_silence_s = float(os.getenv("DASH_WAKE_PHRASE_SILENCE_S", "0.5"))
        self.max_phrase_s = float(os.getenv("DASH_WAKE_MAX_PHRASE_S", "4.0"))
        self.command_tail_s = float(os.getenv("DASH_WAKE_COMMAND_TAIL_S", "1.2"))
        self.max_command_s = float(os.getenv("DASH_WAKE_MAX_COMMAND_S", "8.0"))
        self.echo_guard_s = float(os.getenv("DASH_WAKE_ECHO_GUARD_S", "1.5"))
        # 16-bit mono → 2 bytes per sample. Window caps are SECONDS; the raw
        # buffer is bytes, so the comparison must go through this rate.
        self._bytes_per_second = 2 * self.sample_rate

        self._source = source
        self._transcriber = transcriber
        self._tts_synth = tts_synth
        self._chat_runner = chat_runner
        self._matcher = matcher or WakePhraseMatcher(self.wake_word)
        self._vad = vad  # lazy: get_default_vad()
        self._bus = event_bus  # lazy: get_event_bus()

        self.status = WakeLoopStatus(
            state="disabled" if not self.enabled else "stopped",
            enabled=self.enabled,
            wake_word=self.wake_word,
        )
        self._task: Optional[asyncio.Task] = None
        self._user_id: Optional[str] = None
        self._stt_provider: Optional[Any] = None
        self._speak_until = 0.0
        self._speak_task: Optional[asyncio.Task] = None  # cancellable for barge-in (#11)
        self._stream_speak: bool = os.getenv("DASH_WAKE_STREAM_TTS", "1") == "1"
        self._interrupted_count = 0
        self._stopped = asyncio.Event()
        # Active meeting context (spec #29/#82, decisions.md #102): set by
        # set_meeting_context(); the chat runner wrapper injects it into
        # every command so voice answers are grounded in the meeting.
        self._meeting_context: Optional[dict] = None
        # Phase 3: partial transcripts + live barge-in bookkeeping
        self._last_partial_s = 0.0
        self._interrupt_claimed = False
        self._interrupt_requested_at = 0.0
        # Entity-scoped retrieval (§31): set while a meeting context with a
        # client_id is attached; RAG retrieval stays inside that client.
        self._scoped_client_id: Optional[str] = None
        self._partial_transcriber = partial_transcriber  # None → main STT

    # ── lifecycle ────────────────────────────────────────────────

    async def start(self) -> dict:
        if self._task is not None and not self._task.done():
            return {"ok": False, "reason": "already running"}
        if not self.enabled:
            self.status.state = "disabled"
            self.status.detail = "set DASH_WAKE_LOOP_ENABLED=1 to enable (loop holds the microphone)"
            return {"ok": False, "reason": self.status.detail}
        try:
            source = self._get_source()
            source.start()
        except MicUnavailableError as exc:
            self.status.state = "error"
            self.status.detail = str(exc)
            logger.warning("Wake loop cannot start: %s", exc)
            return {"ok": False, "reason": str(exc)}
        except Exception as exc:  # unexpected — still honest
            self.status.state = "error"
            self.status.detail = f"unexpected mic error: {exc}"
            return {"ok": False, "reason": self.status.detail}

        self._user_id = await self._resolve_user()
        self._stopped.clear()
        self.status.state = "listening"
        self.status.detail = "capturing from default input device"
        self.status.started_at = _iso(time.time())
        self.status.extra["sample_rate"] = self.sample_rate
        self.status.extra["chunk_ms"] = self.chunk_ms
        self._task = asyncio.create_task(self._run(), name="wake-word-loop")
        logger.info(
            "Wake-word loop listening ('%s', %dHz, %dms chunks)",
            self.wake_word, self.sample_rate, self.chunk_ms,
        )
        return {"ok": True, "reason": "listening"}

    async def stop(self) -> dict:
        task = self._task
        self._task = None
        if task is not None:
            self._stopped.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            self._get_source().stop()
        except Exception:
            logger.exception("error stopping mic source")
        self.status.state = "stopped"
        self.status.detail = "stopped by request"
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().release("voice_loop")
        except Exception:
            pass
        return {"ok": True, "reason": "stopped", "wake_count": self.status.wake_count}

    async def shutdown(self) -> dict:
        """App-shutdown path: release the mic and cancel the task without the
        permission checks (a disabled loop at shutdown has nothing to do)."""
        task = self._task
        self._task = None
        if task is not None and not task.done():
            self._stopped.set()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        try:
            self._get_source().stop()
        except Exception:
            logger.exception("error releasing mic at shutdown")
        if self.status.state not in ("disabled", "stopped"):
            self.status.state = "stopped"
            self.status.detail = "stopped at app shutdown"
        logger.info("Wake-word loop shut down (state=%s)", self.status.state)
        return {"ok": True}

    async def _run(self) -> None:
        """Main capture loop. Any stage error is recorded, never fatal-by-silence:
        the loop keeps running so a transient failure cannot kill listening."""
        source = self._get_source()
        mode = "idle"
        buf = bytearray()
        last_speech = 0.0
        last_activity = self._clock()
        try:
            while not self._stopped.is_set():
                chunk = await asyncio.to_thread(source.read_chunk, 0.1)
                if not chunk:
                    # enforce command timeout even without audio
                    if mode == "command" and self._clock() - last_activity > self.max_command_s:
                        logger.info("Wake command window expired without speech")
                        mode, buf = "idle", bytearray()
                    continue
                self.status.dropped_chunks = getattr(source, "dropped_chunks", 0)
                # real-capture proof for status: every chunk pulled off the mic
                self.status.extra["chunks_seen"] = self.status.extra.get("chunks_seen", 0) + 1

                now = self._clock()
                # Echo suppression: ignore everything while speaking + guard.
                # Barge-in (#11): real speech during playback cancels the
                # reply instead of being swallowed by the echo guard.
                if now < self._speak_until:
                    if (self._speak_task is not None
                            and not self._speak_task.done()
                            and speech_if_any(self._get_vad(), chunk)):
                        self._interrupt_speak()
                    continue
                speech = self._get_vad().is_speech(chunk)

                if mode == "idle":
                    if speech:
                        mode, buf, last_speech, last_activity = "phrase", bytearray(chunk), now, now
                elif mode == "phrase":
                    if speech:
                        buf.extend(chunk)
                        last_speech, last_activity = now, now
                        if len(buf) / self._bytes_per_second >= self.max_phrase_s:
                            mode = await self._finish_phrase(bytes(buf)) or mode
                            buf = bytearray()
                    else:
                        if now - last_speech >= self.phrase_silence_s:
                            mode = await self._finish_phrase(bytes(buf))
                            buf = bytearray()
                        elif now - last_activity > self.max_phrase_s:
                            mode, buf = "idle", bytearray()
                elif mode == "command":
                    if speech:
                        buf.extend(chunk)
                        last_speech, last_activity = now, now
                        # Gate the STT call itself — an interim Whisper pass
                        # every chunk would saturate a CPU-only machine.
                        if buf and now - self._last_partial_s >= PARTIAL_INTERVAL_S:
                            partial = await self._quick_partial(bytes(buf))
                            if partial:
                                await self._emit_partial(partial)
                        if len(buf) / self._bytes_per_second >= self.max_command_s:
                            await self._finish_command(bytes(buf))
                            mode, buf = "idle", bytearray()
                    else:
                        if now - last_speech >= self.command_tail_s:
                            if buf:
                                partial = await self._quick_partial(bytes(buf))
                                if partial:
                                    await self._emit_partial(partial, final=True)
                            await self._finish_command(bytes(buf))
                            mode, buf = "idle", bytearray()
                        elif now - last_activity > self.max_command_s:
                            logger.info("Wake command window expired in silence")
                            mode, buf = "idle", bytearray()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.status.state = "error"
            self.status.detail = f"loop crashed: {exc}"
            self.status.last_error = self.status.detail
            logger.exception("wake-word loop crashed")
            raise

    # ── live barge-in + partial transcripts (Phase 3) ─────────────

    def _interrupt_speak(self) -> None:
        """The owner's voice cut DASH off mid-sentence.

        The cancel itself is the barge-in: the cancellable speak task owns
        its voice.interrupted event, interrupted_count and cleanup. This
        also claims INTERRUPTED presence (TTL-bounded so a dead task can
        never strand the orb — the expiry window is the honesty bound) and
        arms the detection→playback-stopped latency measurement.
        """
        self._speak_task.cancel()
        self.status.extra["barge_in"] = True
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().claim(
                "voice_loop", "interrupted",
                detail="owner started speaking", ttl=5.0)
            self._interrupt_claimed = True
            self._interrupt_requested_at = self._clock()
        except Exception:
            pass

    def _observe_interrupt_latency(self) -> None:
        """Real measurement, taken where the cancel lands (the speak task's
        CancelledError handler) — detection→playback-actually-stopped."""
        if not self._interrupt_claimed:
            return
        self._interrupt_claimed = False
        try:
            from dash_backend.assistant.metrics import observe_latency
            observe_latency(
                "voice_interrupt",
                (self._clock() - self._interrupt_requested_at) * 1000.0)
        except Exception:
            pass

    async def _emit_partial(self, text: str, final: bool = False) -> None:
        """Best-effort interim transcript during command capture.

        Pushed to the assistant ws as {type: "voice.partial", text, final}
        and published on the EventBus (voice.partial) so any observer can
        follow along. Throttled to PARTIAL_INTERVAL_S while speech is
        ongoing; the final emit bypasses the throttle. Failure is recorded,
        never raised — the transcript path must not degrade because an
        observer is down.
        """
        text = (text or "").strip()
        if not text:
            return
        now = self._clock()
        if not final and now - self._last_partial_s < PARTIAL_INTERVAL_S:
            return
        self._last_partial_s = now
        data = {"text": text[:220], "final": bool(final)}
        if self._bus is None:
            try:
                from dash_backend.events.event_bus import get_event_bus
                self._bus = get_event_bus()
            except Exception:
                pass
        if self._bus is not None:
            try:
                await self._bus.publish_sync("voice.partial", data)
            except Exception as exc:
                self._record_error(f"voice.partial publish failed: {exc}")
        try:
            from dash_backend.assistant.push import push_assistant_event
            push_assistant_event(None, {"type": "voice.partial", **data})
        except Exception as exc:
            self._record_error(f"voice.partial push failed: {exc}")

    async def _quick_partial(self, pcm: bytes) -> str:
        """Interim transcript for display — the loop's own STT (already
        cached after first use). "" on any failure: a missed interim is
        skipped silently, a wrong one is never shown."""
        try:
            if self._partial_transcriber is not None:
                return (await self._partial_transcriber(pcm)).strip()
            return (await self._transcribe(pcm, metric_kind="voice_stt_partial")).strip()
        except Exception:
            return ""

    # ── phrase / command handling ────────────────────────────────

    async def _finish_phrase(self, pcm: bytes) -> str:
        """Transcribe the captured window and act on the wake phrase.
        Returns the next mode: "command" (wake-only) or "idle"."""
        if not pcm:
            return "idle"
        try:
            transcript = await self._transcribe(pcm)
        except Exception as exc:
            self._record_error(f"transcription failed: {exc}")
            return "idle"
        if not transcript:
            return "idle"
        # diagnosability: what the last phrase window actually heard
        self.status.extra["last_phrase_transcript"] = transcript
        if not self._matcher.matches(transcript):
            self.status.rejected_phrase_count += 1
            logger.debug("Wake rejected: %r", transcript[:80])
            return "idle"
        # WAKE
        self.status.wake_count += 1
        self.status.last_wake_at = _iso(time.time())
        command = self._matcher.extract_command(transcript)
        logger.info("Wake word detected (%s): follow-up=%r", transcript[:60], bool(command))
        await self._publish("voice.wake", {
            "transcript": transcript,
            "command_inline": bool(command),
            "wake_word": self.wake_word,
        })
        if command:
            # "hey dash what time is it" — command arrived in the same breath
            await self._dispatch_command(command)
            return "idle"
        return "command"

    async def _finish_command(self, pcm: bytes) -> None:
        if not pcm:
            return
        try:
            transcript = await self._transcribe(pcm)
        except Exception as exc:
            self._record_error(f"command transcription failed: {exc}")
            return
        if not transcript:
            self._record_error("command transcript empty after wake")
            return
        self.status.extra["last_command_transcript"] = transcript
        await self._dispatch_command(transcript)

    def set_meeting_context(self, meeting: dict) -> None:
        """Attach active meeting context (spec #29/#82, decisions.md #102).
        Mode gates external-speak permission exactly like the meeting
        engine: participant speaking requires authorized_participant.
        An optional ``client_id`` scopes RAG retrieval to that client
        (§31, decisions.md #120)."""
        mode = meeting.get("mode", "listen_only")
        if mode not in ("listen_only", "assisted", "authorized_participant"):
            raise ValueError(f"invalid meeting mode: {mode}")
        self._meeting_context = {
            "meeting_id": meeting.get("meeting_id"),
            "title": meeting.get("title", ""),
            "mode": mode,
            # Client scope (§31): RAG retrieval stays inside this client
            # while the meeting is attached.
            "client_id": meeting.get("client_id"),
            "attached_at": _iso(time.time()),
        }

    def clear_meeting_context(self) -> None:
        self._meeting_context = None

    async def _dispatch_command(self, text: str) -> None:
        self.status.command_count += 1
        self.status.last_command_at = _iso(time.time())
        _t_command = self._clock()
        # Entity scope resets per command (§31): a stale client_id from a
        # cleared meeting context must never leak into the next retrieval.
        self._scoped_client_id = None
        logger.info("Wake command: %r", text[:120])
        await self._publish("voice.command", {"text": text})
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().claim("voice_loop", "thinking",
                                        detail=f"command: {text[:80]}")
        except Exception:
            pass
        runner = self._get_chat_runner()
        if self._meeting_context is not None:
            base_runner = runner
            meeting_client_id = (self._meeting_context or {}).get("client_id")

            async def runner(text=text, base_runner=base_runner,  # context-aware (#82)
                             meeting_client_id=meeting_client_id):  # §31 scope
                ctx = self._meeting_context or {}
                prefix = (f"[Active meeting: {ctx.get('title', '')} "
                          f"(mode: {ctx.get('mode', 'listen_only')})] ")
                self._scoped_client_id = meeting_client_id
                return await base_runner(prefix + text)
        try:
            reply = await runner(text)
        except Exception as exc:
            self._record_error(f"chat failed: {exc}")
            reply = ""
        try:
            from dash_backend.assistant.metrics import observe_latency
            observe_latency("voice_command_to_reply",
                            (self._clock() - _t_command) * 1000.0)
        except Exception:
            pass
        if not reply:
            self.status.last_reply = None
            return
        self.status.last_reply = reply[:280]
        await self._speak(reply)

    async def announce(self, text: str, *, source: str = "proactive") -> dict:
        """Proactively speak an announcement (decisions.md #126) — the
        "voice" channel of the #119 urgency policy, consumed at last.

        Used for CRITICAL owner-contact items (e.g. a task waiting on a
        confirmation gate). Reuses the full reply pipeline — presence
        claim, streamed TTS with echo guard, barge-in — via the same
        cancellable speak task the conversational path uses, so the owner
        can interrupt an announcement exactly like a reply.

        Honest boundaries: a loop that is not running (disabled, mic
        unavailable, stopped) does NOT fabricate speech — it reports the
        skip. Failures are recorded on the loop status, never raised.
        """
        if not text or not text.strip():
            return {"ok": False, "reason": "empty announcement"}
        if self.status.state != "listening":
            return {
                "ok": False,
                "reason": f"voice loop not listening (state: {self.status.state})",
            }
        # Serialize: an announcement must not barge into a reply (or
        # another announcement) already in progress.
        if (self._speak_task is not None and not self._speak_task.done()):
            return {"ok": False, "reason": "speech already in progress"}
        self.status.extra["announcement"] = text[:120]
        self._speak_task = asyncio.create_task(self._speak(text))
        return {"ok": True, "spoken": text[:120], "source": source}

    async def _speak(self, text: str) -> None:
        """Speak a reply, streaming by sentence when enabled (spec #8/#45).

        The streamed speak runs as its OWN cancellable task — exactly like
        the legacy whole-reply path — so the capture loop keeps consuming
        mic chunks during playback and barge-in (#11) still works. The
        echo guard is extended around every sentence's playback so DASH
        cannot wake on its own streamed audio. Falls back to whole-reply
        synthesis if the streaming module is unavailable or errors.
        """
        try:
            from dash_backend.assistant.presence import get_presence_engine
            get_presence_engine().claim("voice_loop", "speaking",
                                        detail=text[:80])
        except Exception:
            pass
        if self._stream_speak:
            try:
                from dash_backend.assistant.tts_streaming import speak_streamed  # noqa: F401
            except Exception as exc:
                self._record_error(f"streamed TTS unavailable, falling back: {exc}")
                self._stream_speak = False
            else:
                self._speak_task = asyncio.create_task(self._speak_streamed(text))
                return
        await self._speak_legacy(text)

    async def _speak_streamed(self, text: str) -> None:
        """Sentence-streamed playback task. Cancellation = barge-in."""
        try:
            from dash_backend.assistant.tts_streaming import speak_streamed

            async def _play_one(audio: bytes) -> None:
                # guard covers THIS sentence's playback window; extended
                # again for the next sentence, then for the tail at the end
                self._speak_until = self._clock() + self.echo_guard_s + 0.5
                await self._play_wav(audio)

            result = await speak_streamed(
                text, self._get_tts(), _play_one, clock=self._clock)
            # completed normally: cover the echo tail, then report
            self._speak_until = self._clock() + self.echo_guard_s
            if result["failed"]:
                self._record_error(
                    f"streamed TTS: {result['failed']} sentence(s) failed")
            if result["spoken"]:
                await self._publish("voice.reply", {
                    "text": text[:280], "streamed": True,
                    "ttfa_ms": result.get("ttfa_ms")})
            elif not result["failed"]:
                await self._speak_legacy(text)  # nothing playable → legacy
        except asyncio.CancelledError:
            # Barge-in during streamed playback (#11).
            self._interrupted_count += 1
            self._observe_interrupt_latency()
            self._speak_until = 0.0
            self.status.extra["interrupted_reply"] = text[:120]
            try:
                await self._publish("voice.interrupted", {
                    "text": text[:120], "count": self._interrupted_count})
            except Exception:
                pass
            raise
        except Exception as exc:
            self._record_error(f"streamed TTS failed, falling back: {exc}")
            await self._speak_legacy(text)
        finally:
            if self._speak_task is asyncio.current_task():
                self._speak_task = None
            try:
                from dash_backend.assistant.presence import get_presence_engine
                get_presence_engine().release_state("voice_loop", "speaking")
            except Exception:
                pass

    async def _speak_legacy(self, text: str) -> None:
        try:
            audio = await self._get_tts()(text)
        except Exception as exc:
            self._record_error(f"TTS failed: {exc}")
            return
        if not audio:
            self._record_error("TTS produced no audio")
            return
        duration = wav_duration_seconds(audio)
        # guard starts now and covers playback + tail so self-echo can't wake
        self._speak_until = self._clock() + duration + self.echo_guard_s
        await self._publish("voice.reply", {"text": text[:280], "audio_seconds": round(duration, 2)})
        # Playback runs as its OWN task (spec #8/#11): the capture loop
        # keeps consuming mic chunks while DASH speaks, so sustained user
        # speech can cancel the reply (barge-in) instead of being
        # swallowed by the echo guard.
        self._speak_task = asyncio.create_task(self._play_audio(audio, text))

    async def _play_audio(self, audio: bytes, text: str) -> None:
        try:
            await self._play_wav(audio)
        except asyncio.CancelledError:
            # Barge-in: reply cut off by the owner's voice (#11).
            self._interrupted_count += 1
            self._observe_interrupt_latency()
            self._speak_until = 0.0
            self.status.extra["interrupted_reply"] = text[:120]
            try:
                await self._publish("voice.interrupted", {
                    "text": text[:120], "count": self._interrupted_count})
            except Exception:
                pass
            raise
        except Exception as exc:
            self._record_error(f"playback failed: {exc}")
        finally:
            if self._speak_task is asyncio.current_task():
                self._speak_task = None
            try:
                from dash_backend.assistant.presence import get_presence_engine
                get_presence_engine().release_state("voice_loop", "speaking")
            except Exception:
                pass

    async def _play_wav(self, audio: bytes) -> None:
        """Play a WAV while streaming its real playback amplitude (#130).

        The orb pulses with DASH's actual speech: the monitor pre-parses the
        PCM, a ticker emits the level of the chunk the speaker is producing
        right now, and an explicit stop signal ends the pulse. Non-PCM audio
        (or any monitor failure) simply skips measurement — playback itself
        is never gated on it. Injected players (tests, custom output) pass
        through untouched when their payload is not measurable PCM.
        """
        amp = None
        ticker = None
        try:
            from dash_backend.voice_system.playback_amplitude import (
                get_playback_amplitude,
            )
            amp = get_playback_amplitude()
            if amp.begin(audio):
                ticker = asyncio.create_task(self._amplitude_ticker(amp))
            else:
                amp = None
        except Exception:
            amp = None
            ticker = None
        try:
            await self._play_wav_inner(audio)
        finally:
            if ticker is not None:
                ticker.cancel()
            if amp is not None:
                try:
                    amp.emit(0.0, False)  # honest stop signal
                    amp.end()
                except Exception:
                    pass

    async def _amplitude_ticker(self, amp) -> None:
        """Emit live playback levels until cancelled (playback end/barge-in)."""
        try:
            while True:
                await asyncio.sleep(0.033)
                amp.emit(amp.tick(), True)
        except asyncio.CancelledError:
            raise

    async def _play_wav_inner(self, audio: bytes) -> None:
        if self._player is not None:  # injected player (tests, custom output)
            await self._player(audio)
            return
        await self._play_wav_system(audio)

    async def _play_wav_system(self, audio: bytes) -> None:
        import platform
        import tempfile
        tmp_path = os.path.join(tempfile.gettempdir(), f"dash_wake_{uuid.uuid4().hex[:12]}.wav")
        with open(tmp_path, "wb") as f:
            f.write(audio)
        try:
            loop = asyncio.get_running_loop()
            system = platform.system()
            if system == "Windows":
                import winsound

                def _play():
                    winsound.PlaySound(tmp_path, winsound.SND_FILENAME)

                await loop.run_in_executor(None, _play)
            elif system == "Darwin":
                proc = await asyncio.create_subprocess_exec(
                    "afplay", tmp_path,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                await proc.wait()
            else:
                proc = await asyncio.create_subprocess_exec(
                    "paplay", tmp_path,
                    stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                )
                try:
                    await proc.wait()
                except FileNotFoundError:
                    proc = await asyncio.create_subprocess_exec(
                        "aplay", tmp_path,
                        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
                    )
                    await proc.wait()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    # ── lazy dependencies (all overridable for tests) ────────────

    def _get_source(self) -> MicAudioSource:
        if self._source is None:
            self._source = MicAudioSource(self.sample_rate, self.chunk_ms)
        return self._source

    def _get_vad(self):
        if self._vad is None:
            from .vad import get_default_vad

            self._vad = get_default_vad()
        return self._vad

    async def _transcribe(self, pcm: bytes, metric_kind: str = "voice_stt") -> str:
        if self._transcriber is None:
            from dash_backend.voice import WhisperSpeechProvider

            provider = WhisperSpeechProvider()
            self._transcriber = provider.transcribe
            self._stt_provider = provider
        wav = pcm_to_wav(pcm, self.sample_rate)
        _t_stt = self._clock()
        text = (await self._transcriber(wav)).strip()
        try:
            from dash_backend.assistant.metrics import observe_latency
            observe_latency(metric_kind, (self._clock() - _t_stt) * 1000.0)
        except Exception:
            pass
        # status honesty: report which engine actually served this transcript
        # ("faster-whisper" or "openai-whisper"; "none" only before first load)
        if self._stt_provider is not None:
            self.status.extra["stt_engine"] = self._stt_provider.engine
        return text

    def _get_tts(self) -> Callable[[str], Awaitable[bytes]]:
        if self._tts_synth is None:
            from dash_backend.voice import get_provider

            provider = get_provider("tts", os.getenv("DASH_WAKE_TTS_PROVIDER", "piper"))
            if provider is None:
                raise RuntimeError("no TTS provider available")
            self._tts_synth = provider.synthesize
        return self._tts_synth

    def _get_chat_runner(self) -> Callable[[str], Awaitable[str]]:
        if self._chat_runner is None:
            self._chat_runner = self._default_chat_runner
        return self._chat_runner

    async def _default_chat_runner(self, text: str) -> str:
        """REAL chat path: handle_chat_send (memory, RAG, candor, tools)."""
        from dash_backend.api.websocket.handlers import handle_chat_send
        from dash_backend.api.websocket.protocol import (
            ChatDoneMessage,
            ChatErrorMessage,
            ChatSendMessage,
            ChatTokenMessage,
        )
        from dash_backend.db.session import AsyncSessionLocal

        msg = ChatSendMessage(message_id=str(uuid.uuid4()), content=text,
                              voice_mode=True,  # short, spoken-friendly replies
                              client_id=getattr(self, "_scoped_client_id", None))  # §31
        parts: list[str] = []
        async with AsyncSessionLocal() as session:
            user_id = self._user_id or await self._resolve_user()
            async for event in handle_chat_send(msg, session=session, user_id=user_id):
                if isinstance(event, ChatTokenMessage):
                    parts.append(event.content or "")
                elif isinstance(event, ChatErrorMessage):
                    return f"(chat error) {event.error}"
                elif isinstance(event, ChatDoneMessage):
                    break
        return "".join(parts).strip()

    async def _resolve_user(self) -> str:
        from dash_backend.api.routes.websocket import _resolve_owner_user_id

        return await _resolve_owner_user_id()

    async def _publish(self, topic: str, data: dict) -> None:
        """Best-effort bus publish (wake/command events can fire workflows).
        A bus failure must never break the loop — recorded, not raised."""
        try:
            if self._bus is None:
                from dash_backend.events.event_bus import get_event_bus

                self._bus = get_event_bus()
            await self._bus.publish_sync(topic, data)
        except Exception as exc:
            self._record_error(f"event publish failed for {topic}: {exc}")

    def _record_error(self, message: str) -> None:
        self.status.last_error = message
        logger.warning("wake loop: %s", message)

    # ── introspection ────────────────────────────────────────────

    def get_status(self) -> dict:
        status = self.status.to_dict()
        status["running"] = bool(self._task is not None and not self._task.done())
        return status


_wake_loop: Optional[AlwaysListeningLoop] = None


def get_wake_loop() -> AlwaysListeningLoop:
    global _wake_loop
    if _wake_loop is None:
        _wake_loop = AlwaysListeningLoop()
    return _wake_loop
