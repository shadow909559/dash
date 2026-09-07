/**
 * DASH AI OS 2.0 Centralized Visual State Engine
 * 
 * This file defines the complete state machine for DASH's visual feedback system.
 * It includes all required states with exact color language and animation parameters.
 */

// ── Core DASH States ────────────────────────────────────────────────────────
export type DASHState =
  | "idle"           // Soft blue, breathing animation
  | "listening"     // Bright orange, wave animation
  | "thinking"      // Orange, rotating animation
  | "speaking"      // Orange, pulse animation
  | "coding"        // Green, flow animation
  | "researching"   // Blue, scan animation
  | "debugging"     // Purple, pulse animation
  | "executing"     // Dynamic gold, activity ring
  | "success"       // Green, expand animation
  | "warning"       // Red-amber, subtle pulse
  | "error"         // Red, shake animation
  | "offline"       // Gray-red, dimmed
  | "connecting"    // Blue, pulsing connection
  | "background";   // Dimmed, minimal animation

// ── Color Language (Exact RGB values as specified) ─────────────────────────────
export interface DASHColor {
  primary: string;      // CSS color string
  rgb: [number, number, number];  // Normalized 0-1 for shaders
  accent: string;
  accentRgb: [number, number, number];
  glow: number;          // Glow intensity 0-1
}

export const DASH_COLORS: Record<DASHState, DASHColor> = {
  idle: {
    primary: "rgba(96, 165, 250, 0.3)",      // Soft blue
    rgb: [0.38, 0.65, 0.98],
    accent: "rgba(144, 202, 249, 0.4)",
    accentRgb: [0.56, 0.79, 0.98],
    glow: 0.35,
  },
  listening: {
    primary: "rgba(255, 150, 0, 0.6)",       // Orange + bright
    rgb: [1.0, 0.59, 0.0],
    accent: "rgba(255, 179, 71, 0.7)",
    accentRgb: [1.0, 0.7, 0.28],
    glow: 0.7,
  },
  thinking: {
    primary: "rgba(255, 140, 0, 0.5)",       // Orange
    rgb: [1.0, 0.55, 0.0],
    accent: "rgba(255, 179, 71, 0.6)",
    accentRgb: [1.0, 0.7, 0.28],
    glow: 0.6,
  },
  speaking: {
    primary: "rgba(255, 150, 0, 0.6)",       // Orange
    rgb: [1.0, 0.59, 0.0],
    accent: "rgba(255, 179, 71, 0.7)",
    accentRgb: [1.0, 0.7, 0.28],
    glow: 0.65,
  },
  coding: {
    primary: "rgba(34, 197, 94, 0.5)",       // Green
    rgb: [0.13, 0.77, 0.37],
    accent: "rgba(74, 222, 128, 0.6)",
    accentRgb: [0.29, 0.87, 0.5],
    glow: 0.6,
  },
  researching: {
    primary: "rgba(59, 130, 246, 0.5)",       // Blue
    rgb: [0.23, 0.51, 0.96],
    accent: "rgba(96, 165, 250, 0.6)",
    accentRgb: [0.38, 0.65, 0.98],
    glow: 0.55,
  },
  debugging: {
    primary: "rgba(168, 85, 247, 0.5)",       // Purple
    rgb: [0.66, 0.33, 0.97],
    accent: "rgba(192, 132, 252, 0.6)",
    accentRgb: [0.75, 0.52, 0.99],
    glow: 0.6,
  },
  executing: {
    primary: "rgba(234, 179, 8, 0.6)",       // Dynamic gold
    rgb: [0.92, 0.7, 0.03],
    accent: "rgba(250, 204, 21, 0.7)",
    accentRgb: [0.98, 0.8, 0.08],
    glow: 0.75,
  },
  success: {
    primary: "rgba(34, 197, 94, 0.6)",       // Green
    rgb: [0.13, 0.77, 0.37],
    accent: "rgba(74, 222, 128, 0.7)",
    accentRgb: [0.29, 0.87, 0.5],
    glow: 0.8,
  },
  warning: {
    primary: "rgba(63, 169, 245, 0.5)",       // Red-amber
    rgb: [0.94, 0.27, 0.27],
    accent: "rgba(251, 146, 60, 0.6)",
    accentRgb: [0.98, 0.57, 0.24],
    glow: 0.65,
  },
  error: {
    primary: "rgba(63, 169, 245, 0.7)",       // Red
    rgb: [0.94, 0.27, 0.27],
    accent: "rgba(248, 113, 113, 0.8)",
    accentRgb: [0.97, 0.44, 0.44],
    glow: 0.85,
  },
  offline: {
    primary: "rgba(107, 114, 128, 0.4)",     // Gray-red
    rgb: [0.42, 0.45, 0.5],
    accent: "rgba(156, 163, 175, 0.5)",
    accentRgb: [0.61, 0.64, 0.69],
    glow: 0.3,
  },
  connecting: {
    primary: "rgba(59, 130, 246, 0.5)",       // Blue pulsing
    rgb: [0.23, 0.51, 0.96],
    accent: "rgba(96, 165, 250, 0.6)",
    accentRgb: [0.38, 0.65, 0.98],
    glow: 0.5,
  },
  background: {
    primary: "rgba(96, 165, 250, 0.2)",      // Dimmed
    rgb: [0.38, 0.65, 0.98],
    accent: "rgba(144, 202, 249, 0.25)",
    accentRgb: [0.56, 0.79, 0.98],
    glow: 0.2,
  },
};

// ── Animation Parameters ─────────────────────────────────────────────────────
export interface DASHAnimation {
  type: "breathing" | "waves" | "rotating" | "pulse" | "flow" | "scan" | "shake" | "expand" | "activity-ring" | "minimal";
  speed: number;           // Animation speed multiplier
  intensity: number;       // Animation intensity 0-1
  turbulence: number;     // Plasma turbulence 0-1
  ringSpeed: number;       // Ring rotation speed
  shellSpeed: number;      // Shell rotation speed
  particleSpeed: number;   // Particle speed multiplier
}

export const DASH_ANIMATIONS: Record<DASHState, DASHAnimation> = {
  idle: {
    type: "breathing",
    speed: 1.0,
    intensity: 0.3,
    turbulence: 0.1,
    ringSpeed: 0.4,
    shellSpeed: 0.6,
    particleSpeed: 0.3,
  },
  listening: {
    type: "waves",
    speed: 1.6,
    intensity: 0.7,
    turbulence: 0.35,
    ringSpeed: 1.6,
    shellSpeed: 1.2,
    particleSpeed: 0.6,
  },
  thinking: {
    type: "rotating",
    speed: 0.9,
    intensity: 0.5,
    turbulence: 0.5,
    ringSpeed: -0.9,
    shellSpeed: 0.9,
    particleSpeed: 0.45,
  },
  speaking: {
    type: "pulse",
    speed: 1.2,
    intensity: 0.6,
    turbulence: 0.4,
    ringSpeed: 1.0,
    shellSpeed: 1.0,
    particleSpeed: 0.5,
  },
  coding: {
    type: "flow",
    speed: 1.1,
    intensity: 0.5,
    turbulence: 0.4,
    ringSpeed: 1.1,
    shellSpeed: 1.4,
    particleSpeed: 0.5,
  },
  researching: {
    type: "scan",
    speed: 1.8,
    intensity: 0.55,
    turbulence: 0.45,
    ringSpeed: 1.8,
    shellSpeed: 1.5,
    particleSpeed: 0.7,
  },
  debugging: {
    type: "pulse",
    speed: 1.0,
    intensity: 0.6,
    turbulence: 0.5,
    ringSpeed: 1.2,
    shellSpeed: 1.6,
    particleSpeed: 0.55,
  },
  executing: {
    type: "activity-ring",
    speed: 2.2,
    intensity: 0.75,
    turbulence: 0.6,
    ringSpeed: 2.2,
    shellSpeed: 1.8,
    particleSpeed: 0.8,
  },
  success: {
    type: "expand",
    speed: 1.0,
    intensity: 0.8,
    turbulence: 0.3,
    ringSpeed: 1.2,
    shellSpeed: 1.0,
    particleSpeed: 0.5,
  },
  warning: {
    type: "pulse",
    speed: 0.8,
    intensity: 0.65,
    turbulence: 0.4,
    ringSpeed: 0.8,
    shellSpeed: 1.0,
    particleSpeed: 0.4,
  },
  error: {
    type: "shake",
    speed: 2.6,
    intensity: 0.85,
    turbulence: 0.8,
    ringSpeed: 2.6,
    shellSpeed: 2.0,
    particleSpeed: 0.9,
  },
  offline: {
    type: "minimal",
    speed: 0.5,
    intensity: 0.3,
    turbulence: 0.1,
    ringSpeed: 0.2,
    shellSpeed: 0.3,
    particleSpeed: 0.2,
  },
  connecting: {
    type: "pulse",
    speed: 1.5,
    intensity: 0.5,
    turbulence: 0.3,
    ringSpeed: 1.5,
    shellSpeed: 1.2,
    particleSpeed: 0.5,
  },
  background: {
    type: "minimal",
    speed: 0.3,
    intensity: 0.2,
    turbulence: 0.05,
    ringSpeed: 0.2,
    shellSpeed: 0.3,
    particleSpeed: 0.2,
  },
};

// ── State Transition Rules ─────────────────────────────────────────────────────
export const STATE_TRANSITIONS: Record<DASHState, DASHState[]> = {
  idle: ["listening", "connecting", "background", "offline"],
  listening: ["thinking", "idle", "error"],
  thinking: ["speaking", "coding", "researching", "debugging", "executing", "idle", "error"],
  speaking: ["idle", "listening", "error"],
  coding: ["executing", "success", "error", "idle", "debugging"],
  researching: ["thinking", "success", "error", "idle"],
  debugging: ["coding", "executing", "success", "error", "idle"],
  executing: ["success", "error", "idle", "warning"],
  success: ["idle", "background"],
  warning: ["idle", "error", "executing"],
  error: ["idle", "offline", "connecting"],
  offline: ["connecting", "idle"],
  connecting: ["idle", "offline"],
  background: ["idle", "listening", "warning"],
};

// ── Helper Functions ─────────────────────────────────────────────────────────
export function isValidTransition(from: DASHState, to: DASHState): boolean {
  return STATE_TRANSITIONS[from].includes(to);
}

export function getStateColor(state: DASHState): DASHColor {
  return DASH_COLORS[state];
}

export function getStateAnimation(state: DASHState): DASHAnimation {
  return DASH_ANIMATIONS[state];
}

// Legacy compatibility: map old states to new DASH states
export function mapLegacyState(legacyState: string): DASHState {
  const mapping: Record<string, DASHState> = {
    "idle": "idle",
    "listening": "listening",
    "thinking": "thinking",
    "talking": "speaking",
    "processing": "executing",
    "waiting": "researching",
    "sleeping": "background",
    "reacting": "executing",
  };
  return mapping[legacyState] || "idle";
}

export function mapLegacyOrbState(orbState: string): DASHState {
  const mapping: Record<string, DASHState> = {
    "standby": "idle",
    "listening": "listening",
    "thinking": "thinking",
    "coding": "coding",
    "searching": "researching",
    "executing": "executing",
    "success": "success",
    "error": "error",
    "serious": "warning",
  };
  return mapping[orbState] || "idle";
}
