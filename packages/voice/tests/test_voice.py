from dash_voice.types import VoiceMode


def test_voice_mode() -> None:
    assert VoiceMode.STT.value == "speech_to_text"
