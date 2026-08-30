export interface ColorPreset {
  id: string;
  name: string;
  hex: string;
  threeColor: number;
  glowClass: string;
  borderClass: string;
  textClass: string;
  bgGlow: string;
}

export type GeometryCoreShape = 'sphere' | 'icosahedron' | 'octahedron' | 'torusKnot' | 'dodecahedron';

export type RenderMode = 'wireframe' | 'solid' | 'points';

export interface HudSettings {
  colorPresetId: string;
  rotationSpeed: number;
  floatAmplitude: number;
  coreShape: GeometryCoreShape;
  renderMode: RenderMode;
  showExtraRings: boolean;
  showParticles: boolean;
  showTargetLock: boolean;
  soundEnabled: boolean;
  ambientHum: boolean;
  cameraDistance: number;
  bloomGlow: boolean;
  autoRotate: boolean;
  pulseSpeed: number;
  activeTab: 'hud' | 'radar' | 'diagnostics' | 'audio';
}

export interface TelemetryData {
  fps: number;
  pitch: number;
  yaw: number;
  roll: number;
  coreTemp: number;
  outputPower: number;
  signalStrength: number;
  syncRatio: number;
  quantumFreq: number;
}

export interface TargetLock {
  id: string;
  x: number;
  y: number;
  worldPos: { x: number; y: number; z: number };
  label: string;
  distance: string;
  timeCreated: number;
}
