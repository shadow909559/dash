/**
 * Shared mic-amplitude producer (#131).
 *
 * ONE place measures any live microphone stream and dispatches the
 * 'micamplitude' window event (0..1 CustomEvent detail) that the home orb,
 * the floating orb, and the voice orb already consume. Before this module
 * the event had no dispatcher at all — the orbs' mic listeners were dead
 * code and only VoicePage's local rAF drove its own orb.
 *
 * Sources register either an AnalyserNode (already wired into an audio
 * chain by the owner, e.g. MicrophoneManager) or a raw MediaStream (a
 * shared internal AudioContext + analyser is created lazily, e.g.
 * MediaRecorder-based capture). Multiple simultaneous sources merge by
 * max-RMS — "any speech" semantics — and the rAF loop runs only while at
 * least one source is live, self-cleaning when tracks end or contexts
 * close so a forgotten registration can never leak a loop.
 */

type SourceEntry = {
  analyser: AnalyserNode;
  buffer: Uint8Array;
  /** Optional teardown for stream-sourced entries (context node disconnect). */
  detach?: () => void;
};

let _seq = 0;
const _sources = new Map<number, SourceEntry>();
let _raf = 0;
let _lastDispatched = -1;
let _framesSinceDispatch = 0;
let _sharedCtx: AudioContext | null = null;

const DISPATCH_EVERY_N_FRAMES = 2; // ~30 Hz — live but not spammy
const VALUE_EPSILON = 0.005;

function getSharedContext(): AudioContext {
  if (!_sharedCtx) {
    const Ctx = window.AudioContext || (window as any).webkitAudioContext;
    _sharedCtx = new Ctx();
  }
  if (_sharedCtx.state === "suspended") {
    void _sharedCtx.resume();
  }
  return _sharedCtx;
}

function rmsOf(analyser: AnalyserNode, buffer: Uint8Array): number {
  analyser.getByteTimeDomainData(buffer as any);
  let sum = 0;
  for (let i = 0; i < buffer.length; i++) {
    const v = (buffer[i] - 128) / 128;
    sum += v * v;
  }
  return Math.sqrt(sum / buffer.length);
}

function removeSource(id: number): void {
  const entry = _sources.get(id);
  if (!entry) return;
  try {
    entry.detach?.();
  } catch {
    /* detach is best-effort */
  }
  _sources.delete(id);
  if (_sources.size === 0) stopLoop();
}

function startLoop(): void {
  if (_raf) return;
  _lastDispatched = -1;
  const frame = () => {
    _raf = requestAnimationFrame(frame);
    if (_sources.size === 0) return;

    // Dead sources remove themselves (ended tracks, closed contexts).
    for (const [id, entry] of _sources) {
      const ctxState = entry.analyser.context.state;
      if (ctxState === "closed") removeSource(id);
    }
    if (_sources.size === 0) return;

    // Max-RMS merge across sources: the loudest live mic wins.
    let maxRms = 0;
    for (const entry of _sources.values()) {
      try {
        const rms = rmsOf(entry.analyser, entry.buffer);
        if (rms > maxRms) maxRms = rms;
      } catch {
        /* a dead node reads as failure — retried next frame */
      }
    }
    // Gamma-corrected level with mild gain: typical speech lands ~0.2-0.9.
    const level = Math.min(1, Math.sqrt(maxRms) * 1.4);

    _framesSinceDispatch++;
    if (_framesSinceDispatch < DISPATCH_EVERY_N_FRAMES) return;
    _framesSinceDispatch = 0;
    const rounded = Math.round(level * 1000) / 1000;
    if (Math.abs(rounded - _lastDispatched) < VALUE_EPSILON) return;
    _lastDispatched = rounded;
    window.dispatchEvent(new CustomEvent("micamplitude", { detail: rounded }));
  };
  _raf = requestAnimationFrame(frame);
}

function stopLoop(): void {
  if (_raf) {
    cancelAnimationFrame(_raf);
    _raf = 0;
  }
  // One explicit zero so consumers decay to idle instead of freezing.
  if (_lastDispatched !== 0) {
    _lastDispatched = 0;
    window.dispatchEvent(new CustomEvent("micamplitude", { detail: 0 }));
  }
}

export interface MicAmplitudeHandle {
  /** Unregister this source. Idempotent; safe to call more than once. */
  stop(): void;
}

/**
 * Register a live mic source. Accepts an existing AnalyserNode (must be
 * receiving audio) or a raw MediaStream (an internal AudioContext and
 * analyser are created and wired for you). When a MediaStream's audio
 * track ends, the source removes itself automatically.
 */
export function registerMicAmplitudeSource(
  source: AnalyserNode | MediaStream,
): MicAmplitudeHandle {
  let entry: SourceEntry;
  if (source instanceof MediaStream) {
    const ctx = getSharedContext();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    const node = ctx.createMediaStreamSource(source);
    node.connect(analyser);
    entry = {
      analyser,
      buffer: new Uint8Array(analyser.fftSize),
      detach: () => {
        try {
          node.disconnect();
        } catch {
          /* already detached */
        }
      },
    };
    // Self-cleanup when the owner stops the tracks (e.g. recorder stop).
    const track = source.getAudioTracks()[0];
    if (track) {
      track.addEventListener("ended", () => {
        for (const [id, e] of _sources) {
          if (e.analyser === analyser) removeSource(id);
        }
      });
    }
  } else {
    entry = { analyser: source, buffer: new Uint8Array(source.fftSize) };
  }
  const id = ++_seq;
  _sources.set(id, entry);
  startLoop();
  let stopped = false;
  return {
    stop() {
      if (stopped) return;
      stopped = true;
      removeSource(id);
    },
  };
}

/** Number of currently registered sources (diagnostics/tests). */
export function micAmplitudeSourceCount(): number {
  return _sources.size;
}
