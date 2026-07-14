import { create } from 'zustand';
import { useAgentStore } from '../agent/agentStore';
import type { VoiceState, VoiceConfig } from './voiceTypes';

const DEFAULT_CONFIG: VoiceConfig = {
  sampleRate: 16000,
  encoding: 'pcm16',
  channels: 1,
};

type MediaResources = {
  stream: MediaStream | null;
  recorder: MediaRecorder | null;
  audioContext: AudioContext | null;
  processor: ScriptProcessorNode | null;
  source: MediaStreamAudioSourceNode | null;
  inputGain: GainNode | null;
};

type VoiceStoreState = {
  voiceState: VoiceState;
  isSupported: boolean;
  permissionState: PermissionState | 'unsupported';
  error: string | null;
  _sequence: number;
  _startedAt: number | null;
  _media: MediaResources;

  init: () => Promise<void>;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
  reset: () => void;
};

export const useVoiceStore = create<VoiceStoreState>((set, get) => {
  // Subscribe to incoming messages to detect backend speaking state
  const unsub = useAgentStore.getState().onMessage((data) => {
    const type = data.type as string | undefined;
    if (type === 'audio_start' || type === 'voice_start' || type === 'speaking') {
      set({ voiceState: 'speaking' });
    } else if (type === 'audio_end' || type === 'voice_end' || type === 'silence') {
      set({ voiceState: 'idle' });
    }
  });

  // Expose unsub on the store so consumers can clean up if needed
  void unsub;

  return {
    voiceState: 'idle' as VoiceState,
    isSupported: checkBrowserSupport(),
    permissionState: 'unsupported' as PermissionState | 'unsupported',
    error: null,
    _sequence: 0,
    _startedAt: null,
    _media: {
      stream: null,
      recorder: null,
      audioContext: null,
      processor: null,
      source: null,
      inputGain: null,
    },

    init: async () => {
      if (!get().isSupported) {
        set({ error: 'Voice is not supported in this browser' });
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        stream.getTracks().forEach((t) => t.stop());
        set({ permissionState: 'granted', error: null });
      } catch (err) {
        const message =
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Microphone permission denied'
            : err instanceof Error
              ? err.message
              : 'Failed to access microphone';
        set({ permissionState: 'denied', error: message });
      }
    },

    startRecording: async () => {
      if (!get().isSupported) {
        set({ error: 'Voice is not supported in this browser' });
        return;
      }

      const agentState = useAgentStore.getState();
      if (agentState.status !== 'connected') {
        set({ error: 'Agent not connected. Voice requires an active connection.' });
        return;
      }

      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          audio: {
            sampleRate: { ideal: DEFAULT_CONFIG.sampleRate },
            channelCount: { ideal: DEFAULT_CONFIG.channels },
            echoCancellation: true,
            noiseSuppression: true,
            autoGainControl: true,
          },
        });

        const audioContext = new AudioContext({ sampleRate: DEFAULT_CONFIG.sampleRate });
        const source = audioContext.createMediaStreamSource(stream);
        const inputGain = audioContext.createGain();
        inputGain.gain.value = 1.0;

        const bufferSize = 4096;
        const processor = audioContext.createScriptProcessor(bufferSize, 1, 1);

        source.connect(inputGain);
        inputGain.connect(processor);
        processor.connect(audioContext.destination);

        const now = Date.now();
        let seq = 0;

        agentState.sendMessage({ type: 'audio_start', timestamp: now });

        processor.onaudioprocess = (event) => {
          const inputData = event.inputBuffer.getChannelData(0);
          const pcm16 = float32ToPcm16(inputData);
          const base64 = arrayBufferToBase64(pcm16.buffer as ArrayBuffer);
          agentState.sendMessage({
            type: 'audio_chunk',
            data: base64,
            sequence: seq++,
            timestamp: Date.now(),
          });
        };

        set({
          voiceState: 'listening',
          _sequence: seq,
          _startedAt: now,
          error: null,
          _media: {
            stream,
            recorder: null,
            audioContext,
            processor,
            source,
            inputGain,
          },
        });
      } catch (err) {
        const message =
          err instanceof DOMException && err.name === 'NotAllowedError'
            ? 'Microphone permission denied'
            : err instanceof Error
              ? err.message
              : 'Failed to start recording';
        set({ error: message, voiceState: 'idle' });
      }
    },

    stopRecording: () => {
      const { _media, _startedAt } = get();

      if (!_media.processor || !_media.stream || !_media.audioContext) {
        return;
      }

      try {
        if (_media.processor && _media.source) {
          _media.processor.disconnect();
          _media.source.disconnect();
        }
        if (_media.inputGain) {
          _media.inputGain.disconnect();
        }
      } catch {
        // Ignore cleanup errors
      }

      _media.stream.getTracks().forEach((t) => t.stop());

      if (_media.audioContext.state !== 'closed') {
        void _media.audioContext.close();
      }

      const now = Date.now();
      const duration = _startedAt ? now - _startedAt : 0;
      useAgentStore.getState().sendMessage({
        type: 'audio_end',
        timestamp: now,
        duration,
      });

      set({
        voiceState: 'idle',
        _startedAt: null,
        _media: {
          stream: null,
          recorder: null,
          audioContext: null,
          processor: null,
          source: null,
          inputGain: null,
        },
      });
    },

    reset: () => {
      const { _media } = get();

      if (_media.stream) {
        _media.stream.getTracks().forEach((t) => t.stop());
      }
      if (_media.audioContext && _media.audioContext.state !== 'closed') {
        void _media.audioContext.close();
      }

      set({
        voiceState: 'idle',
        error: null,
        _sequence: 0,
        _startedAt: null,
        _media: {
          stream: null,
          recorder: null,
          audioContext: null,
          processor: null,
          source: null,
          inputGain: null,
        },
      });
    },
  };
});

// ── Helpers ──────────────────────────────────────────────────────────────

function checkBrowserSupport(): boolean {
  const hasGetUserMedia = !!(navigator.mediaDevices?.getUserMedia);
  const hasAudioContext = typeof AudioContext !== 'undefined' ||
    typeof (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext !== 'undefined';
  // If MediaRecorder is undefined, the typeof check on a global class returns 'function', not 'undefined'.
  // So we check if we're in a browser environment that defines it.
  const hasMediaRecorder = typeof window !== 'undefined' &&
    typeof (window as unknown as { MediaRecorder?: unknown }).MediaRecorder === 'function';
  return hasGetUserMedia && hasAudioContext && hasMediaRecorder;
}

function float32ToPcm16(float32Array: Float32Array): Int16Array {
  const pcm16 = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]));
    pcm16[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
  }
  return pcm16;
}

function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}