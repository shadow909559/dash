# Piper TTS Integration — Implementation Steps

## ✅ Step 1: Create `dash_backend/voice_system/piper_provider.py`
- Implement `PiperTTSProvider` extending `TTSProvider`
- `synthesize()` runs piper.exe subprocess, captures WAV stdout
- Temp file management (create temp WAV, play, delete)
- Non-blocking via `asyncio.create_subprocess_exec`
- Streaming support via `--output-raw`

## ☐ Step 2: Update `dash_backend/voice.py`
- Import PiperTTSProvider
- Register it as `register_provider("tts", "piper", PiperTTSProvider())`

## ☐ Step 3: Update `dash_backend/voice_system/profiles.py`
- Default profile: `tts_provider="piper"`, `tts_voice="ryan"`

## ☐ Step 4: Update `dash_backend/voice_system/service.py`
- VoiceSession: auto-trigger TTS on transcripts via synthesize_and_notify
- Add playback via platform audio (playsound/winsound)
- Track interrupt state

## ☐ Step 5: Update `dash_backend/voice_system/streaming.py`
- Integrate Piper provider for streaming TTS
- Interrupt handling: kill piper subprocess when user speaks

## ☐ Step 6: Update `dash_backend/api/websocket/handlers.py`
- After chat completion (`ChatDoneMessage`), auto-synthesize assistant response
- Stream audio chunks back via WS events

## ☐ Step 7: Update `dash_backend/voice_system/conversation.py`
- Hooks for auto-TTS on conversation responses

