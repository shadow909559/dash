"""Whisper STT provider tests (decisions.md #66).

All hermetic: a fake ``whisper`` module is injected into ``sys.modules``, so
no model download, no ffmpeg call, and no audio fixtures are needed. The
tests pin the honesty contract:

- Whisper is the *default* STT provider when openai-whisper is importable
  (offline + private); speech_recognition (cloud) only defaults when it is not.
- A successful transcription returns the model's text, stripped.
- Any failure (load or transcribe) returns "" — never a fabricated transcript;
  the websocket handler turns "" into a clean voice.stt.error.
- Empty audio returns "" without touching the model.
- ``DASH_WHISPER_MODEL`` selects the model; the provider lazy-loads and caches.
- The temp audio file is always cleaned up, even on failure.
"""

from __future__ import annotations

import sys
import types
from typing import Any

import pytest

import dash_backend.voice as voice_mod
from dash_backend.voice import WhisperSpeechProvider


class _FakeModel:
    def __init__(self, result: Any) -> None:
        self.result = result
        self.calls: list[str] = []

    def transcribe(self, path: str) -> Any:
        self.calls.append(path)
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


@pytest.fixture()
def fake_whisper(monkeypatch: pytest.MonkeyPatch) -> list[_FakeModel]:
    """Inject a fake `whisper` module; returns the list the created models land in.

    The fixture also BLOCKS faster-whisper (None in sys.modules → ImportError)
    so these tests deterministically exercise the openai-whisper fallback
    engine regardless of what is installed on the machine. The faster-whisper
    engine has its own tests below.
    """
    models: list[_FakeModel] = []

    def load_model(name: str) -> _FakeModel:
        model = _FakeModel({"text": "  hello from dash  "})
        model.requested_name = name  # type: ignore[attr-defined]
        models.append(model)
        return model

    module = types.ModuleType("whisper")
    module.load_model = load_model  # type: ignore[attr-defined]
    # Force the fallback engine: None in sys.modules makes the
    # `import faster_whisper` inside _load_model raise ImportError.
    monkeypatch.setitem(sys.modules, "faster_whisper", None)
    monkeypatch.setitem(sys.modules, "whisper", module)
    return models


class TestTranscription:
    @pytest.mark.asyncio
    async def test_transcribes_and_strips(self, fake_whisper: list[_FakeModel]) -> None:
        provider = WhisperSpeechProvider()
        text = await provider.transcribe(b"RIFF-fake-wav-bytes")
        assert text == "hello from dash"
        assert len(fake_whisper) == 1
        # The audio reached the model through a real file path
        assert fake_whisper[0].calls and fake_whisper[0].calls[0].endswith(".wav")

    @pytest.mark.asyncio
    async def test_empty_audio_never_loads_model(self, fake_whisper: list[_FakeModel]) -> None:
        provider = WhisperSpeechProvider()
        assert await provider.transcribe(b"") == ""
        assert fake_whisper == []

    @pytest.mark.asyncio
    async def test_load_failure_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(name: str) -> Any:
            raise RuntimeError("no model available")

        # Block the primary engine too, or the real faster-whisper model
        # would load (and download) before the fake fallback is reached.
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        module = types.ModuleType("whisper")
        module.load_model = boom  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "whisper", module)
        provider = WhisperSpeechProvider()
        # Failure contract: "" — never a fabricated transcript
        assert await provider.transcribe(b"audio") == ""

    @pytest.mark.asyncio
    async def test_transcribe_failure_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        model = _FakeModel(RuntimeError("ffmpeg exploded"))

        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        module = types.ModuleType("whisper")
        module.load_model = lambda name: model  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "whisper", module)
        provider = WhisperSpeechProvider()
        assert await provider.transcribe(b"audio") == ""

    @pytest.mark.asyncio
    async def test_model_cached_and_temp_file_cleaned(
        self, fake_whisper: list[_FakeModel], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        provider = WhisperSpeechProvider()
        await provider.transcribe(b"first")
        await provider.transcribe(b"second")
        # Lazy model loads exactly once and is reused
        assert len(fake_whisper) == 1
        # Both temp files were cleaned up
        for call_path in fake_whisper[0].calls:
            import os

            assert not os.path.exists(call_path)

    @pytest.mark.asyncio
    async def test_serializes_concurrent_calls(self, fake_whisper: list[_FakeModel]) -> None:
        import asyncio

        provider = WhisperSpeechProvider()
        results = await asyncio.gather(
            provider.transcribe(b"a"), provider.transcribe(b"b")
        )
        assert results == ["hello from dash", "hello from dash"]
        # The lock means one shared model, not one per race
        assert len(fake_whisper) == 1


class TestModelSelection:
    def test_default_model_name(self) -> None:
        assert WhisperSpeechProvider().model_name == "base.en"

    def test_env_overrides_model(
        self, monkeypatch: pytest.MonkeyPatch, fake_whisper: list[_FakeModel]
    ) -> None:
        monkeypatch.setenv("DASH_WHISPER_MODEL", "small")
        assert WhisperSpeechProvider().model_name == "small"

    def test_constructor_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DASH_WHISPER_MODEL", "small")
        assert WhisperSpeechProvider(model_name="tiny").model_name == "tiny"


class TestRegistration:
    @pytest.fixture()
    def clean_speech_registry(self):
        saved = dict(voice_mod._PROVIDERS["speech"])
        # Start from an empty registry: the real module import already
        # registered whisper on machines where it is installed, and the
        # register function adds — it never clears stale keys.
        voice_mod._PROVIDERS["speech"] = {}
        yield
        voice_mod._PROVIDERS["speech"] = saved

    def test_whisper_default_when_available(self, clean_speech_registry: None) -> None:
        voice_mod._register_stt_providers(whisper_available=True)
        assert voice_mod.get_provider("speech", "whisper") is not None
        default = voice_mod.get_provider("speech", "default")
        assert isinstance(default, WhisperSpeechProvider)
        # Cloud fallback still reachable under its own name. The cloud
        # provider needs the optional speech_recognition package (not
        # declared in CI); skip when it is genuinely absent — the
        # availability contract itself is pinned above.
        try:
            import speech_recognition  # noqa: F401
        except ImportError:
            pytest.skip("speech_recognition not installed (optional cloud STT)")
        assert voice_mod.get_provider("speech", "speech_recognition") is not None

    def test_speech_recognition_defaults_without_whisper(
        self, clean_speech_registry: None
    ) -> None:
        try:
            import speech_recognition  # noqa: F401
        except ImportError:
            pytest.skip("speech_recognition not installed (optional cloud STT)")
        voice_mod._register_stt_providers(whisper_available=False)
        from dash_backend.voice import _SpeechRecognitionProvider

        assert isinstance(
            voice_mod.get_provider("speech", "default"), _SpeechRecognitionProvider
        )
        # And whisper is NOT registered when unavailable
        assert voice_mod.get_provider("speech", "whisper") is None

    def test_current_registry_uses_whisper_default(self) -> None:
        # The real module registration on machines WITH a local whisper
        # engine: the default must be the offline provider. On boxes without
        # one (e.g. CI) the honest registration result is the noop provider —
        # pin that too, mirroring _register_stt_providers' detection.
        default = voice_mod.get_provider("speech", "default")
        try:
            import faster_whisper  # noqa: F401
            available = True
        except ImportError:
            available = False
        if not available:
            try:
                import whisper  # noqa: F401
                available = True
            except ImportError:
                available = False
        if available:
            assert isinstance(default, WhisperSpeechProvider)
        else:
            from dash_backend.voice import _NoopSpeechProvider

            assert isinstance(default, _NoopSpeechProvider)


class TestFasterWhisperEngine:
    """The primary engine: faster-whisper (CTranslate2).

    All hermetic: a fake `faster_whisper` module is injected; its model
    returns a lazy segment iterator exactly like the real engine's API
    (`segments, info = model.transcribe(path)`).
    """

    @pytest.fixture()
    def fake_faster_whisper(self, monkeypatch: pytest.MonkeyPatch):
        models: list[Any] = []

        class _Seg:
            def __init__(self, text: str) -> None:
                self.text = text

        class _FakeFWModel:
            def __init__(self, name: str, device: str = "cpu", **kwargs: Any) -> None:
                self.requested_name = name
                self.device = device
                self.kwargs = kwargs
                self.calls: list[str] = []
                self.result: Any = [_Seg("hello "), _Seg("from dash")]

            def transcribe(self, path: str):
                self.calls.append(path)
                if isinstance(self.result, Exception):
                    raise self.result
                return iter(self.result), {"language": "en", "duration": 1.0}

        def factory(name: str, device: str = "cpu", **kwargs: Any) -> _FakeFWModel:
            m = _FakeFWModel(name, device, **kwargs)
            models.append(m)
            return m

        module = types.ModuleType("faster_whisper")
        module.WhisperModel = factory  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "faster_whisper", module)
        return models

    @pytest.mark.asyncio
    async def test_transcribes_via_segments_and_reports_engine(
        self, fake_faster_whisper: list[Any]
    ) -> None:
        provider = WhisperSpeechProvider()
        text = await provider.transcribe(b"RIFF-fake-wav-bytes")
        assert text == "hello from dash"
        # The engine that actually ran is reported, never guessed
        assert provider.engine == "faster-whisper"
        assert fake_faster_whisper[0].device == "cpu"
        assert fake_faster_whisper[0].calls[0].endswith(".wav")

    @pytest.mark.asyncio
    async def test_model_cached_across_calls(
        self, fake_faster_whisper: list[Any]
    ) -> None:
        provider = WhisperSpeechProvider()
        await provider.transcribe(b"first")
        await provider.transcribe(b"second")
        assert len(fake_faster_whisper) == 1
        assert provider.engine == "faster-whisper"

    @pytest.mark.asyncio
    async def test_compute_type_env_override(
        self, fake_faster_whisper: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DASH_WHISPER_COMPUTE", "int8")
        provider = WhisperSpeechProvider()
        await provider.transcribe(b"audio")
        assert fake_faster_whisper[0].kwargs.get("compute_type") == "int8"

    @pytest.mark.asyncio
    async def test_auto_compute_passes_no_override(
        self, fake_faster_whisper: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("DASH_WHISPER_COMPUTE", "auto")
        provider = WhisperSpeechProvider()
        await provider.transcribe(b"audio")
        assert "compute_type" not in fake_faster_whisper[0].kwargs

    @pytest.mark.asyncio
    async def test_engine_load_failure_falls_back_to_openai(
        self, fake_faster_whisper: list[Any], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # faster-whisper import succeeds but the model load explodes
        # (bad download, incompatible wheel) → honest fallback to
        # openai-whisper, and the fallback engine is what gets reported.
        def broken_factory(name: str, device: str = "cpu", **kwargs: Any) -> Any:
            raise RuntimeError("ctranslate2 wheel incompatible")

        import types as _types

        module = _types.ModuleType("faster_whisper")
        module.WhisperModel = broken_factory  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "faster_whisper", module)

        class _FakeOpenAIModel:
            def transcribe(self, path: str) -> Any:
                return {"text": "  fallback worked  "}

        openai_mod = _types.ModuleType("whisper")
        openai_mod.load_model = lambda name: _FakeOpenAIModel()  # type: ignore[attr-defined]
        monkeypatch.setitem(sys.modules, "whisper", openai_mod)

        provider = WhisperSpeechProvider()
        assert await provider.transcribe(b"audio") == "fallback worked"
        assert provider.engine == "openai-whisper"
