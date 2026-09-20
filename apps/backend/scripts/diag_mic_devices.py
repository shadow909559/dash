"""Per-device mic sweep: which input device actually hears the speakers?"""

from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import sounddevice as sd


def rms_dbfs(samples: np.ndarray) -> float:
    x = samples.astype(np.float64) / 32768.0
    r = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
    return 20 * np.log10(max(r, 1e-10))


def play_tone(duration: float = 2.0, freq: float = 440.0, gain: float = 0.5):
    t = np.linspace(0, duration, int(48000 * duration), endpoint=False)
    wave = (gain * np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
    import winsound
    import wave as wavemod

    tmp = Path(__file__).parent / "_tone.wav"
    with wavemod.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(48000)
        w.writeframes(wave)
    threading.Thread(target=lambda: winsound.PlaySound(str(tmp), winsound.SND_FILENAME), daemon=True).start()
    return tmp


def measure(device_index: int, name: str) -> float:
    """Try native-ish sample rates; read via the stream's blocking API."""
    for rate in (16000, 44100, 48000):
        try:
            with sd.InputStream(device=device_index, samplerate=rate, channels=1,
                                dtype="int16", blocksize=rate // 10) as stream:
                frames = []
                deadline = time.time() + 2.0
                while time.time() < deadline:
                    data, _overflowed = stream.read(rate // 10)
                    frames.append(data.copy())
                buf = np.concatenate(frames) if frames else np.zeros((1, 1), dtype="int16")
                db = rms_dbfs(buf)
                peak = rms_dbfs(np.array([[int(np.abs(buf).max())]], dtype="int16"))
                print(f"  [{device_index:>2}] {name[:52]:<52} @{rate}  peak {peak:>7.1f} dBFS  rms {db:>7.1f} dBFS")
                return db
        except Exception:
            continue
    print(f"  [{device_index:>2}] {name[:52]:<52} ERROR: no workable sample rate")
    return -200.0


def main() -> None:
    devices = sd.query_devices()
    inputs = [(i, d) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]
    sweep_seconds = 2.0 * max(1, len(inputs)) + 2.0  # measure window + settle, per device
    print(f"== input device sweep ({len(inputs)} inputs, ~{sweep_seconds:.0f}s of tone) ==")
    tone_tmp = play_tone(duration=sweep_seconds)
    best = (-200.0, None)
    try:
        time.sleep(0.4)
        for i, d in inputs:
            db = measure(i, d.get("name", "?"))
            if db > best[0]:
                best = (db, (i, d.get("name", "?")))
    finally:
        tone_tmp.unlink(missing_ok=True)
    print(
        f"\nHEARING BEST: [{best[1][0]}] {best[1][1]} at {best[0]:.1f} dBFS"
        if best[1]
        else "\nnothing heard"
    )


if __name__ == "__main__":
    main()
