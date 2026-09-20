"""STT engine benchmark: faster-whisper vs openai-whisper on identical audio.

The provider (dash_backend.voice.WhisperSpeechProvider) prefers
faster-whisper and falls back to openai-whisper; this script measures what
that preference buys on THIS machine, honestly:

- One shared WAV (real speech synthesized locally via Piper TTS) is written
  to a single temp file; both engines transcribe that exact file.
- Each engine gets a warmup run (absorbs model load/first-touch), then N
  timed runs; load time is reported separately, never mixed into steady-
  state latency.
- Accuracy is word error rate against the known source text — and both
  transcripts are printed verbatim so the numbers can be judged, not just
  trusted.

Usage:  python scripts/bench_stt_engines.py [--runs 5] [--model base.en]
        [--audio path/to.wav] [--text "exact words in that wav"]
"""

from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

DEFAULT_TEXT = "Hey Dash, what time is it? Summarize my morning, then remind me to stretch at noon."


def wer(reference: str, hypothesis: str) -> float:
    """Word error rate: Levenshtein distance over word lists / len(ref)."""
    ref = reference.lower().split()
    hyp = hypothesis.lower().split()
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(
                prev[j] + 1,        # deletion
                cur[j - 1] + 1,     # insertion
                prev[j - 1] + (r != h),  # substitution
            )
        prev = cur
    return prev[-1] / len(ref)


def build_audio(out_path: Path, text: str) -> bool:
    """Synthesize the benchmark sentence with the local Piper TTS (real speech,
    deterministic, fully offline). Returns False if Piper is unavailable."""
    from dash_backend.voice import get_provider

    provider = get_provider("tts", "piper")

    async def synth() -> bytes:
        return await provider.synthesize(text)

    audio = asyncio.run(synth())
    if not audio:
        return False
    out_path.write_bytes(audio)
    print(f"audio: {len(audio)} bytes of real Piper speech written to {out_path.name}")
    return True


def bench_engine(label: str, wav_path: str, runs: int, compute: str = "auto") -> dict:
    """Warmup + timed runs for one engine; load time kept separate."""
    t0 = time.perf_counter()
    if label == "faster-whisper":
        from faster_whisper import WhisperModel

        kwargs = {"compute_type": compute} if compute and compute != "auto" else {}
        model = WhisperModel(_model_name(), device="cpu", **kwargs)

        def run() -> str:
            segments, _info = model.transcribe(wav_path)
            return "".join(s.text for s in segments).strip()
    else:
        import whisper

        model = whisper.load_model(_model_name())

        def run() -> str:
            return str(model.transcribe(wav_path).get("text", "")).strip()

    load_s = time.perf_counter() - t0
    first = run()  # warmup: first-touch decode paths, excluded from timing
    latencies: list[float] = []
    last = first
    for _ in range(runs):
        t = time.perf_counter()
        last = run()
        latencies.append(time.perf_counter() - t)
    return {
        "engine": label,
        "load_s": load_s,
        "warmup_text": first,
        "latencies": latencies,
        "text": last,
    }


_MODEL: str | None = None


def _model_name() -> str:
    return _MODEL or "base.en"


def main() -> int:
    global _MODEL
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--model", default="base.en")
    ap.add_argument("--compute", default="auto", help="faster-whisper compute_type (e.g. int8)")
    ap.add_argument("--audio", default=None, help="existing WAV to use instead of synthesizing")
    ap.add_argument("--text", default=DEFAULT_TEXT, help="exact words in the audio (for WER)")
    args = ap.parse_args()
    _MODEL = args.model

    tmp = None
    try:
        if args.audio:
            wav = Path(args.audio)
            if not wav.exists():
                print(f"ERROR: {wav} not found")
                return 1
        else:
            fd, tmp = tempfile.mkstemp(suffix=".wav", prefix="dash_bench_")
            os.close(fd)
            wav = Path(tmp)
            if not build_audio(wav, args.text):
                print("ERROR: Piper TTS unavailable — pass --audio to benchmark a real file")
                return 1

        print(f"\n== STT benchmark: model '{args.model}', {args.runs} timed runs each, "
              f"identical file for both engines ==\n")
        results = []
        for label in ("faster-whisper", "openai-whisper"):
            print(f"[{label}] loading…", flush=True)
            r = bench_engine(label, str(wav), args.runs, args.compute)
            results.append(r)
            mean = statistics.mean(r["latencies"])
            print(f"    load {r['load_s']:6.2f}s   mean {mean:6.2f}s   "
                  f"min {min(r['latencies']):5.2f}s   max {max(r['latencies']):5.2f}s")
            print(f"    transcript: {r['text']!r}\n", flush=True)

        fw, ow = results
        fw_wer = wer(args.text, fw["text"])
        ow_wer = wer(args.text, ow["text"])
        speedup = statistics.mean(ow["latencies"]) / max(statistics.mean(fw["latencies"]), 1e-9)
        print("== verdict ==")
        print(f"speedup (openai-whisper / faster-whisper): {speedup:.2f}x")
        print(f"WER  faster-whisper: {fw_wer:.3f}   openai-whisper: {ow_wer:.3f}   "
              f"(reference: {args.text!r})")
        return 0
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
