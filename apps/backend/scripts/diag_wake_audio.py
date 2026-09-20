"""Acoustic-path diagnosis for the wake loop.

Answers three questions with measurements, not guesses:
  1. Does the default mic capture Piper's speech?  (per-chunk RMS stats)
  2. Does the energy VAD (threshold 500) see it as speech?
  3. Can Whisper base.en transcribe the captured audio?
"""

from __future__ import annotations

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dash_backend.voice_system.always_listening import MicAudioSource, pcm_to_wav
from dash_backend.voice_system.vad import EnergyVAD
from dash_backend.voice import WhisperSpeechProvider


def rms(chunk: bytes) -> float:
    import array
    a = array.array("h")
    a.frombytes(chunk[: len(chunk) // 2 * 2])
    if not a:
        return 0.0
    return sum(abs(x) for x in a) / len(a)


async def main() -> None:
    src = MicAudioSource()
    src.start()
    vad = EnergyVAD(threshold=500.0)
    whisper = WhisperSpeechProvider()

    # let the stream settle, drain backlog
    time.sleep(0.3)
    while src.read_chunk(timeout=0.05):
        pass

    import winsound
    from dash_backend.voice import get_provider

    piper = get_provider("tts", "piper")
    wav = await piper.synthesize("Hey DASH, can you hear me clearly now")
    tmp = Path(__file__).parent / "_diag_utterance.wav"
    tmp.write_bytes(wav)
    print(f"speaking ({len(wav)} bytes of audio)...")
    t0 = time.time()
    winsound.PlaySound(str(tmp), winsound.SND_FILENAME)
    print(f"playback took {time.time()-t0:.1f}s")
    tmp.unlink(missing_ok=True)

    # collect 4 more seconds of tail
    chunks: list[bytes] = []
    deadline = time.time() + 4.0
    while time.time() < deadline:
        c = src.read_chunk(timeout=0.1)
        if c:
            chunks.append(c)
    src.stop()

    energies = [rms(c) for c in chunks]
    speech_flags = [vad.is_speech(c) for c in chunks]
    n = len(chunks)
    print(f"\ncaptured {n} chunks in ~{n*0.1:.1f}s")
    if not energies:
        print("NOTHING CAPTURED — mic dead")
        return
    print(f"rms min/avg/max: {min(energies):.0f}/{sum(energies)/len(energies):.0f}/{max(energies):.0f}  (VAD threshold 500)")
    print(f"chunks over 500: {sum(1 for e in energies if e > 500)}/{n}")
    print(f"vad speech flags: {sum(speech_flags)}/{n}")

    # Whisper on the loudest contiguous region (or everything if quiet)
    buf = b"".join(chunks)
    print(f"\ntotal audio: {len(buf)/32000:.1f}s — sending to Whisper base.en ...")
    t0 = time.time()
    text = await whisper.transcribe(pcm_to_wav(buf))
    dt = time.time() - t0
    print(f"whisper ({dt:.1f}s) -> {text!r}")


if __name__ == "__main__":
    asyncio.run(main())
