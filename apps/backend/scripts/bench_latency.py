"""DASH end-to-end latency benchmark (#136). Real measurements only.

Sections (all on THIS machine, against REAL providers):
  STT   WhisperSpeechProvider on real synthesized speech: cold (load incl.)
        vs warm (model resident), 3 warm runs, median.
  LLM   Ollama /api/chat stream=True: TTFT + ~100-token total, cold
        (explicit unload first) vs warm (resident, keep_alive path).
  TTS   Windows SAPI (pyttsx3) synth of a 12-word sentence.
  REST  GET /health and GET /desktop/applications/search on the live
        backend, first (cold cache) vs subsequent (warm cache).

Writes scripts/bench_latency_results.json for the report.

Usage:
    py scripts/bench_latency.py [--fast] [--base-url http://127.0.0.1:8000]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import urllib.request
import wave
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

RESULTS: dict[str, float] = {}
SAMPLES: dict[str, list[float]] = {}


def rec(name: str, ms: float) -> None:
    RESULTS[name] = round(ms, 1)
    print(f"  {name:52s} {ms:9.1f} ms")


def rec_samples(name: str, values: list[float]) -> float:
    med = statistics.median(values)
    SAMPLES[name] = [round(v, 1) for v in values]
    rec(name, med)
    return med


# ── audio: real synthesized speech ───────────────────────────────────
BENCH_TEXT = "DASH what is the weather in Tokyo tomorrow morning"


def make_speech_wav(out_path: Path) -> None:
    """Real SAPI speech rendered to a 16 kHz mono WAV."""
    import pyttsx3

    engine = pyttsx3.init()
    engine.setProperty("rate", 175)
    tmp = out_path.with_suffix(".tmp.wav")
    engine.save_to_file(BENCH_TEXT, str(tmp))
    engine.runAndWait()
    # SAPI writes its own format; re-encode to 16 kHz mono PCM16 via wave if
    # already PCM it is copied verbatim (whisper/ffmpeg accepts either).
    data = tmp.read_bytes()
    out_path.write_bytes(data)
    tmp.unlink(missing_ok=True)
    print(f"  audio: {len(data)} bytes, text: {BENCH_TEXT!r}")


# ── STT ──────────────────────────────────────────────────────────────
def bench_stt(wav_path: Path) -> None:
    from dash_backend.voice import WhisperSpeechProvider

    async def run() -> None:
        prov = WhisperSpeechProvider()  # fresh instance = cold model
        audio = wav_path.read_bytes()

        t0 = time.perf_counter()
        text_cold = await prov.transcribe(audio)
        cold_ms = (time.perf_counter() - t0) * 1000
        rec("stt.cold_ms (model load + decode)", cold_ms)
        print(f"    cold text: {text_cold!r} engine={prov.engine}")

        warms = []
        texts = []
        for _ in range(3):
            t = time.perf_counter()
            txt = await prov.transcribe(audio)
            warms.append((time.perf_counter() - t) * 1000)
            texts.append(txt)
        med = rec_samples("stt.warm_ms (model resident)", warms)
        print(f"    warm text: {texts[-1]!r}")
        RESULTS["stt.warm_median_ms"] = round(med, 1)

    asyncio.run(run())


# ── LLM ──────────────────────────────────────────────────────────────
def _ollama_base() -> str:
    from dash_backend.config import get_settings

    return get_settings().ollama_base_url.rstrip("/")


def _ollama_model() -> str:
    from dash_backend.config import get_settings

    s = get_settings()
    return s.ai_model or s.ollama_model or "dash-finetuned:latest"


def _unload_model(base: str, model: str) -> None:
    req = urllib.request.Request(
        f"{base}/api/generate",
        data=json.dumps({"model": model, "keep_alive": 0}).encode(),
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req, timeout=30).read()


def bench_llm(fast: bool) -> None:
    base = _ollama_base()
    model = _ollama_model()
    print(f"  model={model} base={base}")

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly one short sentence about the weather."}],
        "stream": True,
        "options": {"num_predict": 100},
    }
    if not getattr(__import__("dash_backend.config", fromlist=["get_settings"]).get_settings(), "ollama_thinking", False):
        payload["think"] = False

    def stream_once() -> tuple[float, float, str]:
        t0 = time.perf_counter()
        ttft = None
        chunks: list[str] = []
        req = urllib.request.Request(
            f"{base}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as resp:
            for line in resp:
                if not line.strip():
                    continue
                evt = json.loads(line)
                if evt.get("done") is False or "message" in evt:
                    piece = (evt.get("message") or {}).get("content", "")
                    if piece and ttft is None:
                        ttft = (time.perf_counter() - t0) * 1000
                    chunks.append(piece)
        total_ms = (time.perf_counter() - t0) * 1000
        return ttft or total_ms, total_ms, "".join(chunks).strip()

    if not fast:
        _unload_model(base, model)
        ttft, total, text = stream_once()
        rec("llm.ttft_cold_ms (weights from disk/RAM)", ttft)
        rec("llm.total_cold_ms (~100 tokens)", total)
        print(f"    cold text: {text[:80]!r}")

    warms_t, warms_ttft = [], []
    text = ""
    for _ in range(3):
        ttft, total, text = stream_once()
        warms_ttft.append(ttft)
        warms_t.append(total)
    rec_samples("llm.ttft_warm_ms (resident model)", warms_ttft)
    rec_samples("llm.total_warm_ms (~100 tokens)", warms_t)
    print(f"    warm text: {text[:80]!r}")


# ── TTS ──────────────────────────────────────────────────────────────
def bench_tts(out_dir: Path) -> None:
    import pyttsx3

    engine = pyttsx3.init()
    wav = out_dir / "bench_tts_out.wav"
    t0 = time.perf_counter()
    engine.save_to_file("Sure, I scheduled that meeting for tomorrow at ten and sent the invite.", str(wav))
    engine.runAndWait()
    rec("tts.sapi_first_audio_ms (12-word sentence)", (time.perf_counter() - t0) * 1000)


# ── REST against the live backend ────────────────────────────────────
def bench_rest(base_url: str) -> None:
    def get(path: str) -> tuple[int, bytes]:
        t0 = time.perf_counter()
        with urllib.request.urlopen(f"{base_url}{path}", timeout=30) as r:
            body = r.read()
            code = r.status
        return code, body

    code, _ = get("/api/v1/desktop/health")
    print(f"  backend status: {code}")

    # health: 5 samples
    vals = []
    for _ in range(5):
        t = time.perf_counter()
        get("/api/v1/desktop/health")
        vals.append((time.perf_counter() - t) * 1000)
    rec_samples("rest.health_warm_ms", vals)

    # app search: first hit may scan (cold TTL cache), then warm
    t = time.perf_counter()
    code, body = get("/api/v1/desktop/applications/search?q=dash")
    rec("rest.appsearch_cold_ms (may include disk scan)", (time.perf_counter() - t) * 1000)
    n = len(json.loads(body)) if code == 200 and body.startswith(b"[") else -1
    print(f"    search 'dash' results: {n}")
    vals = []
    for _ in range(5):
        t = time.perf_counter()
        get("/api/v1/desktop/applications/search?q=dash")
        vals.append((time.perf_counter() - t) * 1000)
    rec_samples("rest.appsearch_warm_ms", vals)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip cold LLM unload/run")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000")
    ap.add_argument("--skip-rest", action="store_true")
    args = ap.parse_args()

    out_dir = Path(__file__).resolve().parent
    wav = out_dir / "bench_speech.wav"

    print("== STT (WhisperSpeechProvider) ==")
    make_speech_wav(wav)
    bench_stt(wav)

    print("== LLM (Ollama streaming chat) ==")
    bench_llm(args.fast)

    print("== TTS (Windows SAPI) ==")
    bench_tts(out_dir)

    if not args.skip_rest:
        print("== REST (live backend) ==")
        try:
            bench_rest(args.base_url)
        except Exception as exc:
            print(f"  REST section skipped: {exc}")

    (out_dir / "bench_latency_results.json").write_text(
        json.dumps({"results": RESULTS, "samples": SAMPLES}, indent=2), encoding="utf-8"
    )
    print("\nresults -> scripts/bench_latency_results.json")


if __name__ == "__main__":
    main()
