// DASH Orb State System
// Maps each AI state to a target color and motion behavior.
// Colors are the "identity" of DASH's holographic orb.
// Now integrated with DASH 2.0 centralized state engine

import type { DASHState } from "@/stores/dashState";
import { getStateColor, getStateAnimation } from "@/stores/dashState";

export type OrbState =
  | "standby"
  | "listening"
  | "thinking"
  | "coding"
  | "searching"
  | "executing"
  | "success"
  | "error"
  | "serious";

export interface OrbVisualParams {
  /** Primary hue as RGB 0-1 for shader uniforms */
  color: [number, number, number];
  /** Secondary/accent hue */
  accent: [number, number, number];
  /** Core glow intensity (0-1) */
  glowIntensity: number;
  /** Particle speed multiplier */
  particleSpeed: number;
  /** Breathing speed of the core */
  breathingSpeed: number;
  /** Pulse intensity of the plasma */
  pulseIntensity: number;
  /** Ring rotation speed (rad/s) */
  ringSpeed: number;
  /** Inner shell rotation speed */
  shellSpeed: number;
  /** How active/turbulent the plasma is */
  turbulence: number;
  /** Bloom strength */
  bloom: number;
}

export const ORB_STATES: Record<OrbState, OrbVisualParams> = {
  standby: {
    color: [0.38, 0.65, 0.98], // Blue
    accent: [0.2, 0.5, 1.0],
    glowIntensity: 0.35,
    particleSpeed: 0.3,
    breathingSpeed: 1.0,
    pulseIntensity: 0.1,
    ringSpeed: 0.4,
    shellSpeed: 0.6,
    turbulence: 0.1,
    bloom: 0.9,
  },
  listening: {
    color: [0.55, 0.85, 1.0], // Light Blue
    accent: [0.3, 0.7, 1.0],
    glowIntensity: 0.7,
    particleSpeed: 0.6,
    breathingSpeed: 0.8,
    pulseIntensity: 0.3,
    ringSpeed: 1.6,
    shellSpeed: 1.2,
    turbulence: 0.35,
    bloom: 1.4,
  },
  thinking: {
    color: [1.0, 0.55, 0.2], // Orange
    accent: [1.0, 0.7, 0.3],
    glowIntensity: 0.6,
    particleSpeed: 0.45,
    breathingSpeed: 1.1,
    pulseIntensity: 0.2,
    ringSpeed: -0.9,
    shellSpeed: 0.9,
    turbulence: 0.5,
    bloom: 1.2,
  },
  coding: {
    color: [0.65, 0.35, 1.0], // Purple
    accent: [0.85, 0.5, 1.0],
    glowIntensity: 0.6,
    particleSpeed: 0.5,
    breathingSpeed: 1.0,
    pulseIntensity: 0.15,
    ringSpeed: 1.1,
    shellSpeed: 1.4,
    turbulence: 0.4,
    bloom: 1.2,
  },
  searching: {
    color: [0.2, 1.0, 0.5], // Green
    accent: [0.4, 1.0, 0.7],
    glowIntensity: 0.55,
    particleSpeed: 0.7,
    breathingSpeed: 0.9,
    pulseIntensity: 0.25,
    ringSpeed: 1.8,
    shellSpeed: 1.5,
    turbulence: 0.45,
    bloom: 1.3,
  },
  executing: {
    color: [1.0, 0.8, 0.2], // Gold
    accent: [1.0, 0.9, 0.4],
    glowIntensity: 0.75,
    particleSpeed: 0.8,
    breathingSpeed: 0.7,
    pulseIntensity: 0.35,
    ringSpeed: 2.2,
    shellSpeed: 1.8,
    turbulence: 0.6,
    bloom: 1.6,
  },
  success: {
    color: [0.2, 1.0, 0.6], // Emerald
    accent: [0.4, 1.0, 0.8],
    glowIntensity: 0.8,
    particleSpeed: 0.5,
    breathingSpeed: 0.75,
    pulseIntensity: 0.3,
    ringSpeed: 1.2,
    shellSpeed: 1.0,
    turbulence: 0.3,
    bloom: 1.5,
  },
  error: {
    color: [1.0, 0.15, 0.2], // Crimson
    accent: [1.0, 0.3, 0.3],
    glowIntensity: 0.85,
    particleSpeed: 0.9,
    breathingSpeed: 0.5,
    pulseIntensity: 0.5,
    ringSpeed: 2.6,
    shellSpeed: 2.0,
    turbulence: 0.8,
    bloom: 1.8,
  },
  serious: {
    color: [1.0, 0.1, 0.1], // Red
    accent: [1.0, 0.25, 0.2],
    glowIntensity: 0.9,
    particleSpeed: 0.7,
    breathingSpeed: 0.6,
    pulseIntensity: 0.4,
    ringSpeed: 2.0,
    shellSpeed: 1.6,
    turbulence: 0.7,
    bloom: 1.7,
  },
};

// Map the existing AI store state/emotion to an OrbState
export function mapStoreToOrbState(
  aiState: string,
  emotion: string
): OrbState {
  switch (aiState) {
    case "listening":
      return "listening";
    case "thinking":
      return "thinking";
    case "talking":
      return "listening"; // Speaking state uses listening visual for voice feedback
    case "processing":
      return "executing";
    case "reacting":
      return "executing";
    case "waiting":
      return "searching";
    case "sleeping":
      return "standby";
    case "idle":
      return "standby";
    default:
      break;
  }

  // Emotion fallback
  switch (emotion) {
    case "focused":
    case "thinking":
      return "coding";
    case "curious":
    case "listening":
      return "listening";
    case "speaking":
      return "listening"; // Speaking emotion maps to listening visual
    case "happy":
    case "excited":
      return "success";
    case "concerned":
    case "confused":
      return "error";
    case "surprised":
      return "searching";
    case "calm":
      return "standby";
    default:
      return "standby";
  }
}

// Map DASH 2.0 state to legacy OrbState for backward compatibility
export function mapDASHStateToOrbState(dashState: DASHState): OrbState {
  const mapping: Record<DASHState, OrbState> = {
    idle: "standby",
    listening: "listening",
    thinking: "thinking",
    speaking: "listening",
    coding: "coding",
    researching: "searching",
    debugging: "coding",
    executing: "executing",
    success: "success",
    warning: "serious",
    error: "error",
    offline: "serious",
    connecting: "listening",
    background: "standby",
  };
  return mapping[dashState] || "standby";
}

// Get visual parameters from DASH 2.0 state engine
export function getDASHStateVisuals(dashState: DASHState): OrbVisualParams {
  const color = getStateColor(dashState);
  const animation = getStateAnimation(dashState);
  
  return {
    color: color.rgb,
    accent: color.accentRgb,
    glowIntensity: color.glow,
    particleSpeed: animation.particleSpeed,
    breathingSpeed: animation.speed,
    pulseIntensity: animation.intensity,
    ringSpeed: animation.ringSpeed,
    shellSpeed: animation.shellSpeed,
    turbulence: animation.turbulence,
    bloom: color.glow * 2,
  };
}

// Linear interpolation between two vectors
export function lerpVec3(
  a: [number, number, number],
  b: [number, number, number],
  t: number
): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

// Linear interpolation for scalar values
export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}
