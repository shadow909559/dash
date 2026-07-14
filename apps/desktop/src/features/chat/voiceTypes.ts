export type VoiceState = 'idle' | 'listening' | 'speaking';

export type VoiceMessage =
  | { type: 'audio_start'; timestamp: number }
  | { type: 'audio_chunk'; data: string; sequence: number; timestamp: number }
  | { type: 'audio_end'; timestamp: number; duration: number };

export type VoiceConfig = {
  sampleRate: number;
  encoding: 'pcm16' | 'opus';
  channels: number;
};