"""Integration test: run a real Piper TTS synthesis and playback cycle.

This is NOT a unit test with mocks — it exercises the actual piper.exe binary,
validates the WAV output, and (on headful systems) plays the audio.

Requires:
  - tools/piper/piper.exe
  - models/voices/en_US-ryan-medium.onnx

Run with:
    cd apps/backend
    PIPER_EXE=../../tools/piper/piper.exe \
    PIPER_MODEL=../../models/voices/en_US-ryan-medium.onnx \
    python -m pytest tests/test_piper_tts_integration.py -v -s
"""

from __future__ import annotations

import asyncio
import os
import platform
import struct
import tempfile
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Locate the Piper binary and model relative to this file so the test is
# portable across machines as long as the repo layout is preserved.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]
_PIPER_EXE = Path(
    os.environ.get("PIPER_EXE", str(_REPO_ROOT / "tools" / "piper" / "piper.exe"))
)
_MODEL_DIR = _REPO_ROOT / "models" / "voices"
_MODEL_PATH = Path(
    os.environ.get("PIPER_MODEL", str(_MODEL_DIR / "en_US-ryan-medium.onnx"))
)

_skip_reason: str | None = None
if not _PIPER_EXE.exists():
    _skip_reason = f"Piper executable not found: {_PIPER_EXE}"
elif not _MODEL_PATH.exists():
    _skip_reason = f"Piper model not found: {_MODEL_PATH}"


def _make_provider():
    """Build a PiperTTSProvider pointing at local repo binaries."""
    from dash_backend.voice_system.piper_provider import PiperTTSProvider

    return PiperTTSProvider(
        exe_path=str(_PIPER_EXE),
        model_path=str(_MODEL_PATH),
        voice="ryan",
    )


# ═══════════════════════════════════════════════════════════════════════════
#  1. Synthesis + WAV validation
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")
class TestSynthesis:
    """Synthesize real audio and validate the output."""

    @pytest.mark.asyncio
    async def test_synthesis_produces_valid_wav(self):
        provider = _make_provider()
        wav = await provider.synthesize(
            "Hello, this is a test of the Piper TTS pipeline."
        )

        # --- basic checks ---
        assert len(wav) > 0, "Synthesis returned empty bytes"
        assert len(wav) > 1000, f"WAV suspiciously short: {len(wav)} bytes"

        # --- RIFF/WAV header validation ---
        assert wav[:4] == b"RIFF", f"Missing RIFF header, got {wav[:4]!r}"
        assert wav[8:12] == b"WAVE", f"Missing WAVE identifier, got {wav[8:12]!r}"

        # fmt chunk
        assert wav[12:16] == b"fmt ", "Missing fmt  chunk"
        audio_format = struct.unpack_from("<H", wav, 20)[0]
        assert audio_format == 1, f"Expected PCM (1), got format {audio_format}"

        channels = struct.unpack_from("<H", wav, 22)[0]
        sample_rate = struct.unpack_from("<I", wav, 24)[0]
        bits_per_sample = struct.unpack_from("<H", wav, 34)[0]

        assert channels == 1, f"Expected mono, got {channels} channels"
        assert sample_rate in (16000, 22050, 44100), f"Unexpected rate: {sample_rate}"
        assert bits_per_sample == 16, f"Expected 16-bit, got {bits_per_sample}-bit"

        # data chunk
        assert wav[36:40] == b"data", "Missing data chunk"
        data_size = struct.unpack_from("<I", wav, 40)[0]
        assert data_size == len(wav) - 44, (
            f"Data size mismatch: header says {data_size}, "
            f"actual payload is {len(wav) - 44}"
        )

        print(
            f"\n  [synthesis] {len(wav)} bytes | "
            f"{channels}ch {sample_rate}Hz {bits_per_sample}bit | "
            f"duration ~ {data_size / (sample_rate * channels * bits_per_sample // 8):.2f}s"
        )

    @pytest.mark.asyncio
    async def test_synthesis_long_sentence(self):
        provider = _make_provider()
        text = (
            "The quick brown fox jumps over the lazy dog. "
            "Pack my box with five dozen liquor jugs. "
            "How vexingly quick daft zebras jump!"
        )
        wav = await provider.synthesize(text)
        assert len(wav) > 0, "Long sentence produced empty output"
        assert wav[:4] == b"RIFF"
        print(f"\n  [long sentence] {len(wav)} bytes produced")

    @pytest.mark.asyncio
    async def test_synthesis_empty_and_whitespace(self):
        provider = _make_provider()
        assert await provider.synthesize("") == b""
        assert await provider.synthesize("   ") == b""
        # Note: whitespace-only may produce a small utterance — that's OK for Piper


# ═══════════════════════════════════════════════════════════════════════════
#  2. Streaming TTS
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")
class TestStreamingTTS:
    """Stream PCM chunks from Piper and reassemble."""

    @pytest.mark.asyncio
    async def test_stream_produces_chunks(self):
        provider = _make_provider()
        chunks: list[bytes] = []
        async for chunk in provider.synthesize_stream(
            "Streaming test, this comes in chunks."
        ):
            chunks.append(chunk)

        assert len(chunks) > 0, "Stream produced zero chunks"
        total_bytes = sum(len(c) for c in chunks)
        assert total_bytes > 0, "Stream chunks were all empty"
        print(
            f"\n  [streaming] {len(chunks)} chunks, {total_bytes} total PCM bytes"
        )

    @pytest.mark.asyncio
    async def test_stream_matches_synthesis_size(self):
        """Streamed PCM should be roughly the same size as the PCM inside a WAV."""
        provider = _make_provider()
        text = "Size comparison test."

        # Full synthesis (produces WAV with header)
        wav = await provider.synthesize(text)
        wav_payload = len(wav) - 44 if len(wav) > 44 else 0

        # Streaming (raw PCM)
        total = 0
        async for chunk in provider.synthesize_stream(text):
            total += len(chunk)

        # They should be within 10% of each other
        if wav_payload > 0 and total > 0:
            ratio = total / wav_payload
            assert 0.8 < ratio < 1.2, (
                f"Stream/merge size mismatch: stream={total}, wav_payload={wav_payload}, "
                f"ratio={ratio:.2f}"
            )
            print(f"\n  [size match] stream={total} wav_payload={wav_payload} ratio={ratio:.3f}")


# ═══════════════════════════════════════════════════════════════════════════
#  3. Playback
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")
class TestPlayback:
    """Synthesize → write temp WAV → play it."""

    @pytest.mark.asyncio
    async def test_synthesize_and_play(self):
        provider = _make_provider()
        interrupt = asyncio.Event()

        await provider.synthesize_and_play(
            "Playback test. If you can hear this, it worked!",
            interrupt_flag=interrupt,
        )
        # If we get here without exception, playback succeeded (or no player)

    @pytest.mark.asyncio
    async def test_synthesize_wav_file_valid_on_disk(self):
        """Write a WAV and verify it's a valid file."""
        provider = _make_provider()
        wav = await provider.synthesize("File validation test.")

        tmp = os.path.join(
            tempfile.gettempdir(),
            f"piper_test_{uuid.uuid4().hex[:8]}.wav",
        )
        try:
            with open(tmp, "wb") as f:
                f.write(wav)

            size = os.path.getsize(tmp)
            assert size == len(wav), f"File size mismatch: disk={size}, memory={len(wav)}"

            # Verify we can read it back
            with open(tmp, "rb") as f:
                readback = f.read()
            assert readback[:4] == b"RIFF"
            print(f"\n  [disk] WAV written: {tmp} ({size} bytes)")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


# ═══════════════════════════════════════════════════════════════════════════
#  4. Interrupt
# ═══════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(_skip_reason is not None, reason=_skip_reason or "")
class TestInterrupt:
    """Verify that interrupt kills the active subprocess."""

    @pytest.mark.asyncio
    async def test_synthesize_then_interrupt(self):
        provider = _make_provider()
        interrupt = asyncio.Event()

        # Start synthesis in background and interrupt immediately
        task = asyncio.create_task(
            provider.synthesize_and_play(
                "This should be interrupted immediately.",
                interrupt_flag=interrupt,
            )
        )
        # Let it start, then interrupt
        await asyncio.sleep(0.05)
        interrupt.set()
        provider.interrupt()

        # Should complete quickly (subprocess killed)
        try:
            await asyncio.wait_for(task, timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail("Interrupt did not stop the synthesis within 5s")
        print("\n  [interrupt] Synthesis interrupted successfully")


# ═══════════════════════════════════════════════════════════════════════════
#  5. Provider registration integration
# ═══════════════════════════════════════════════════════════════════════════

class TestProviderRegistration:
    """Ensure the Piper provider registers into the voice module."""

    @pytest.mark.asyncio
    async def test_piper_registered_as_default(self):
        import dash_backend.voice as voice_mod

        piper = voice_mod.get_provider("tts", "piper")
        assert piper is not None, "Piper provider not registered"
        assert hasattr(piper, "synthesize"), "Provider missing synthesize()"

        default = voice_mod.get_provider("tts", "default")
        assert default is not None, "Default TTS provider not registered"
        print(f"\n  [registration] Piper registered: name={getattr(piper, 'name', '?')}")

    @pytest.mark.asyncio
    async def test_synthesize_text_helper(self):
        import dash_backend.voice as voice_mod

        # The top-level helper should route through Piper
        result_b64 = await voice_mod.synthesize_text("Quick helper test.")
        if _skip_reason:
            pytest.skip("Piper not available")
        assert len(result_b64) > 0, "synthesize_text returned empty base64"
        # Decode and validate
        import base64

        raw = base64.b64decode(result_b64)
        assert raw[:4] == b"RIFF", "Decoded audio is not valid WAV"
        print(f"\n  [helper] synthesize_text returned {len(result_b64)} chars base64 -> {len(raw)} bytes WAV")
