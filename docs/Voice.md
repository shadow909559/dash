# Voice System

## Overview

DASH provides a complete voice interaction subsystem with speech-to-text (STT), text-to-speech (TTS), wake word detection, voice activity detection (VAD), and streaming audio processing.

## Components

### Speech-to-Text (STT)

- Provider abstraction (supports OpenAI Whisper, local models)
- Streaming transcription support
- Language detection
- Punctuation restoration

### Text-to-Speech (TTS)

- Provider abstraction (supports OpenAI TTS, local engines)
- Voice selection
- Speed and pitch control
- Streaming audio output

### Wake Word Detection

- Configurable wake word (default: "Hey DASH")
- Pre/post wake word buffering
- Low false-positive rate
- Hotword model management

### Voice Activity Detection (VAD)

- Silence detection for end-of-utterance
- Configurable threshold and timeout
- Pre-speech buffering for capture

### Streaming Processor

- WebSocket-based audio streaming
- Real-time transcription with interim results
- Interrupt handling (stop/resume)
- Audio format conversion

## Provider Configuration

```python
# STT Provider
DASH_STT_PROVIDER=openai  # or "local"
DASH_OPENAI_API_KEY=sk-...

# TTS Provider  
DASH_TTS_PROVIDER=openai  # or "local"
DASH_TTS_VOICE=alloy      # alloy, echo, fable, nova, shimmer

# Wake Word
DASH_WAKE_WORD=hey_dash
DASH_WAKE_WORD_SENSITIVITY=0.5

# VAD
DASH_VAD_THRESHOLD=0.5
DASH_VAD_TIMEOUT_MS=1500
