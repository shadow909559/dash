"""Piper TTS provider — local, fast, offline neural TTS.

Runs piper.exe as a subprocess, captures raw WAV audio from stdout,
optionally streams audio chunks for low-latency playback, and provides
playback management (interrupt, temp file cleanup).

Integrates into the existing provider architecture via
``dash_backend.voice.register_provider("tts", "piper", ...)``.
"""

from __future__ import annotations

import asyncio
import os
import platform
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import AsyncIterator, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────

PIPER_EXE = Path(os.environ.get("PIPER_EXE", r"C:\AI\Piper\piper.exe"))
PIPER_MODEL_DIR = Path(
    os.environ.get("PIPER_MODEL_DIR", r"C:\AI\Piper\models")
)
DEFAULT_MODEL = os.environ.get(
    "PIPER_MODEL", str(PIPER_MODEL_DIR / "en_US-ryan-high.onnx")
)

# Validated at import time so we fail fast
if not PIPER_EXE.exists():
    logger.warning("Piper executable not found at %s", PIPER_EXE)
if not Path(DEFAULT_MODEL).exists():
    logger.warning("Piper model not found at %s", DEFAULT_MODEL)


# ── Provider ───────────────────────────────────────────────────────────


class PiperTTSProvider:
    """Piper neural TTS provider.

    Implements the ``TTSProvider`` interface from
    ``dash_backend.voice.TTSProvider`` (``synthesize(text) -> bytes``).

    Attributes:
        name: Provider identifier used by the voice subsystem registry.
        voice: The Piper voice/model identifier.
    """

    name: str = "piper"
    voice: str = "ryan"

    def __init__(
        self,
        exe_path: str | Path = PIPER_EXE,
        model_path: str | Path = DEFAULT_MODEL,
        voice: str = "ryan",
    ):
        self._exe = Path(exe_path)
        self._model = Path(model_path)
        self.voice = voice
        self._active_process: asyncio.subprocess.Process | None = None
        self._temp_files: list[str] = []

    # ── Primary TTS interface ──────────────────────────────────────────

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio bytes.

        Runs piper.exe, reads raw WAV from stdout, returns the complete
        WAV bytes (including the RIFF/WAV header).
        """
        if not text or not text.strip():
            logger.debug("Empty text — returning empty bytes")
            return b""

        text = text.strip()

        logger.debug(
            "Piper: synthesizing %d chars with model=%s",
            len(text),
            self._model.name,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self._exe),
                "--model", str(self._model),
                "--output-raw",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

            self._active_process = proc

            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=text.encode("utf-8")),
                timeout=60.0,
            )

            self._active_process = None

            if proc.returncode != 0:
                err_msg = stderr.decode("utf-8", errors="replace").strip()
                logger.error(
                    "Piper failed (code=%d): %s",
                    proc.returncode,
                    err_msg,
                )
                return b""

            if not stdout:
                logger.warning("Piper produced empty output")
                return b""

            # Piper --output-raw produces 16-bit PCM without WAV headers.
            # We need to prepend a WAV header for standard playback.
            wav_bytes = self._pcm_to_wav(stdout)

            logger.debug(
                "Piper: generated %d bytes of WAV audio",
                len(wav_bytes),
            )
            return wav_bytes

        except asyncio.TimeoutError:
            logger.error("Piper synthesis timed out after 60s")
            self._kill_active()
            return b""
        except FileNotFoundError:
            logger.error("Piper executable not found at %s", self._exe)
            return b""
        except Exception:
            logger.exception("Piper synthesis failed unexpectedly")
            return b""
        finally:
            self._active_process = None

    # ── Streaming TTS ──────────────────────────────────────────────────

    async def synthesize_stream(
        self, text: str, chunk_size: int = 4096
    ) -> AsyncIterator[bytes]:
        """Stream raw PCM audio chunks from Piper.

        Yields 16-bit PCM chunks as they arrive from the subprocess.
        The caller is responsible for reconstructing or prepending a
        WAV header if needed.

        Args:
            text: Text to synthesize.
            chunk_size: Approximate number of PCM bytes per yield.

        Yields:
            Raw 16-bit PCM audio chunks.
        """
        if not text or not text.strip():
            return

        text = text.strip()

        try:
            proc = await asyncio.create_subprocess_exec(
                str(self._exe),
                "--model", str(self._model),
                "--output-raw",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                stdin=asyncio.subprocess.PIPE,
            )

            self._active_process = proc

            # Write text to stdin and close
            stdin = proc.stdin
            if stdin:
                stdin.write(text.encode("utf-8"))
                await stdin.drain()
                stdin.close()

            # Read stdout in chunks
            while True:
                chunk = await proc.stdout.read(chunk_size)
                if not chunk:
                    break
                yield chunk

            await proc.wait()

            if proc.returncode != 0:
                stderr = await proc.stderr.read()
                logger.error(
                    "Piper stream failed (code=%d): %s",
                    proc.returncode,
                    stderr.decode("utf-8", errors="replace"),
                )

        except Exception:
            logger.exception("Piper streaming failed")
        finally:
            self._active_process = None

    # ── Playback helpers ───────────────────────────────────────────────

    async def synthesize_and_play(
        self,
        text: str,
        interrupt_flag: asyncio.Event | None = None,
    ) -> None:
        """Synthesize and play audio, supporting interruption.

        Creates a temporary WAV file, plays it with platform audio,
        then deletes it. Checks ``interrupt_flag`` before and during
        playback so the caller can stop TTS when the user speaks.

        Args:
            text: Text to speak.
            interrupt_flag: If set, playback is cancelled.
        """
        if not text or not text.strip():
            return

        if interrupt_flag and interrupt_flag.is_set():
            return

        wav_bytes = await self.synthesize(text)
        if not wav_bytes:
            return

        if interrupt_flag and interrupt_flag.is_set():
            return

        # Write temp WAV file
        tmp_path = os.path.join(
            tempfile.gettempdir(),
            f"dash_tts_{uuid.uuid4().hex[:12]}.wav",
        )
        try:
            with open(tmp_path, "wb") as f:
                f.write(wav_bytes)
            self._temp_files.append(tmp_path)

            # Play the audio
            await self._play_wav(tmp_path, interrupt_flag)

        except Exception:
            logger.exception("Failed to play Piper audio")
        finally:
            # Cleanup temp file
            self._cleanup_temp(tmp_path)

    # ── Interrupt support ──────────────────────────────────────────────

    def interrupt(self) -> None:
        """Kill the active Piper subprocess immediately.

        Called when the user starts speaking during TTS playback.
        """
        self._kill_active()

    def _kill_active(self) -> None:
        proc = self._active_process
        if proc is not None and proc.returncode is None:
            try:
                if platform.system() == "Windows":
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                        capture_output=True,
                        timeout=5,
                    )
                else:
                    proc.kill()
                logger.debug("Piper process killed (pid=%d)", proc.pid)
            except Exception:
                logger.exception("Failed to kill Piper process")
        self._active_process = None

    # ── Private helpers ────────────────────────────────────────────────

    @staticmethod
    def _pcm_to_wav(pcm_data: bytes, sample_rate: int = 22050) -> bytes:
        """Prepend a RIFF/WAV header to raw 16-bit PCM data.

        Piper outputs 16-bit mono PCM at 22050 Hz by default.
        """
        data_size = len(pcm_data)
        # WAV header is 44 bytes
        header = bytearray(44)

        # RIFF chunk
        header[0:4] = b"RIFF"
        header[4:8] = (36 + data_size).to_bytes(4, "little")
        header[8:12] = b"WAVE"

        # fmt chunk
        header[12:16] = b"fmt "
        header[16:20] = (16).to_bytes(4, "little")  # chunk size
        header[20:22] = (1).to_bytes(2, "little")  # PCM format
        header[22:24] = (1).to_bytes(2, "little")  # num channels (mono)
        header[24:28] = sample_rate.to_bytes(4, "little")  # sample rate
        byte_rate = sample_rate * 1 * 16 // 8
        header[28:32] = byte_rate.to_bytes(4, "little")
        block_align = 1 * 16 // 8
        header[32:34] = block_align.to_bytes(2, "little")
        header[34:36] = (16).to_bytes(2, "little")  # bits per sample

        # data chunk
        header[36:40] = b"data"
        header[40:44] = data_size.to_bytes(4, "little")

        return bytes(header) + pcm_data

    async def _play_wav(
        self,
        wav_path: str,
        interrupt_flag: asyncio.Event | None = None,
    ) -> None:
        """Play a WAV file using platform audio.

        On Windows uses winsound (blocking but runs in executor).
        On macOS uses afplay. On Linux uses aplay/paplay.

        Checks ``interrupt_flag`` periodically.
        """
        if interrupt_flag and interrupt_flag.is_set():
            return

        system = platform.system()

        try:
            if system == "Windows":
                import winsound

                loop = asyncio.get_running_loop()

                def _play():
                    if interrupt_flag and interrupt_flag.is_set():
                        return
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME)

                await loop.run_in_executor(None, _play)

            elif system == "Darwin":
                proc = await asyncio.create_subprocess_exec(
                    "afplay", wav_path,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                while True:
                    try:
                        await asyncio.wait_for(
                            proc.wait(), timeout=0.2
                        )
                        break
                    except asyncio.TimeoutError:
                        if interrupt_flag and interrupt_flag.is_set():
                            proc.kill()
                            break

            else:
                # Linux: try paplay then aplay
                player = None
                for candidate in ["paplay", "aplay"]:
                    try:
                        proc = await asyncio.create_subprocess_exec(
                            candidate, wav_path,
                            stdout=asyncio.subprocess.DEVNULL,
                            stderr=asyncio.subprocess.DEVNULL,
                        )
                        player = candidate
                        break
                    except FileNotFoundError:
                        continue

                if player is None:
                    logger.warning("No audio player found on Linux")
                    return

                while True:
                    try:
                        await asyncio.wait_for(
                            proc.wait(), timeout=0.2
                        )
                        break
                    except asyncio.TimeoutError:
                        if interrupt_flag and interrupt_flag.is_set():
                            proc.kill()
                            break

        except Exception:
            logger.exception("Failed to play audio")

    def _cleanup_temp(self, path: str) -> None:
        """Delete a single temp file if it exists."""
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug("Deleted temp audio: %s", path)
            if path in self._temp_files:
                self._temp_files.remove(path)
        except Exception:
            logger.exception("Failed to delete temp file %s", path)

    def cleanup_all_temp(self) -> None:
        """Delete all tracked temporary audio files."""
        for path in list(self._temp_files):
            self._cleanup_temp(path)
        self._temp_files.clear()
