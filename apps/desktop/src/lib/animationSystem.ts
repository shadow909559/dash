import { useState, useEffect } from "react";

/**
 * DASH Animation System
 * 
 * Centralized animation state management for the DASH core and UI elements.
 * Provides smooth transitions between different application states.
 */

export type DASHState = 
  | "idle" 
  | "listening" 
  | "thinking" 
  | "responding" 
  | "speaking" 
  | "researching" 
  | "executing" 
  | "error";

export interface AnimationConfig {
  duration: number;
  easing: string;
  keyframes: Keyframe[];
}

export interface StateAnimation {
  state: DASHState;
  animation: AnimationConfig;
}

// Animation configurations for each state
const STATE_ANIMATIONS: Record<DASHState, AnimationConfig> = {
  idle: {
    duration: 2000,
    easing: "ease-in-out",
    keyframes: [
      { transform: "scale(1)", opacity: "0.8" },
      { transform: "scale(1.05)", opacity: "1" },
      { transform: "scale(1)", opacity: "0.8" },
    ],
  },
  listening: {
    duration: 1500,
    easing: "ease-out",
    keyframes: [
      { transform: "scale(1)", opacity: "0.6" },
      { transform: "scale(1.2)", opacity: "1" },
      { transform: "scale(1)", opacity: "0.6" },
    ],
  },
  thinking: {
    duration: 1000,
    easing: "linear",
    keyframes: [
      { transform: "rotate(0deg)" },
      { transform: "rotate(360deg)" },
    ],
  },
  responding: {
    duration: 800,
    easing: "ease-out",
    keyframes: [
      { transform: "scale(1)", opacity: "0.8" },
      { transform: "scale(1.3)", opacity: "1" },
      { transform: "scale(1)", opacity: "0.8" },
    ],
  },
  speaking: {
    duration: 400,
    easing: "ease-in-out",
    keyframes: [
      { transform: "scale(1)" },
      { transform: "scale(1.1)" },
      { transform: "scale(1)" },
    ],
  },
  researching: {
    duration: 2000,
    easing: "ease-in-out",
    keyframes: [
      { transform: "scale(1) rotate(0deg)", opacity: "0.7" },
      { transform: "scale(1.1) rotate(180deg)", opacity: "1" },
      { transform: "scale(1) rotate(360deg)", opacity: "0.7" },
    ],
  },
  executing: {
    duration: 500,
    easing: "ease-out",
    keyframes: [
      { transform: "scale(1)", opacity: "0.8" },
      { transform: "scale(1.2)", opacity: "1" },
      { transform: "scale(1)", opacity: "0.8" },
    ],
  },
  error: {
    duration: 500,
    easing: "ease-in-out",
    keyframes: [
      { transform: "translateX(0)" },
      { transform: "translateX(-10px)" },
      { transform: "translateX(10px)" },
      { transform: "translateX(0)" },
    ],
  },
};

class AnimationController {
  private currentState: DASHState = "idle";
  private previousState: DASHState = "idle";
  private animations: Map<string, Animation> = new Map();
  private listeners: Set<(state: DASHState) => void> = new Set();

  constructor() {
    // Initialize with idle state
    this.currentState = "idle";
  }

  /**
   * Transition to a new state with animation
   */
  transitionTo(newState: DASHState): void {
    if (this.currentState === newState) return;

    this.previousState = this.currentState;
    this.currentState = newState;

    // Notify listeners
    this.notifyListeners();

    // Apply animations to registered elements
    this.applyStateAnimation(newState);
  }

  /**
   * Get current state
   */
  getCurrentState(): DASHState {
    return this.currentState;
  }

  /**
   * Get previous state
   */
  getPreviousState(): DASHState {
    return this.previousState;
  }

  /**
   * Register an element for animation
   */
  registerElement(elementId: string, element: HTMLElement): void {
    // Don't actually register animations for now - we'll use CSS animations instead
    // This avoids the Web Animation API compatibility issues
    this.animations.set(elementId, null as any);
  }

  /**
   * Unregister an element
   */
  unregisterElement(elementId: string): void {
    const animation = this.animations.get(elementId);
    if (animation) {
      animation.cancel();
      this.animations.delete(elementId);
    }
  }

  /**
   * Subscribe to state changes
   */
  subscribe(listener: (state: DASHState) => void): () => void {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  /**
   * Get animation config for a state
   */
  getAnimationConfig(state: DASHState): AnimationConfig {
    return STATE_ANIMATIONS[state];
  }

  /**
   * Apply animation to a specific element
   */
  private applyStateAnimation(state: DASHState, elementId?: string): void {
    // For now, we don't apply Web Animations - we'll use CSS animations instead
    // This avoids compatibility issues and keeps the system simpler
    // The state transitions are handled via React state updates and CSS classes
  }

  /**
   * Notify all listeners of state change
   */
  private notifyListeners(): void {
    this.listeners.forEach(listener => listener(this.currentState));
  }

  /**
   * Clean up all animations
   */
  cleanup(): void {
    this.animations.forEach(animation => animation.cancel());
    this.animations.clear();
    this.listeners.clear();
  }
}

// Singleton instance
let animationController: AnimationController | null = null;

export function getAnimationController(): AnimationController {
  if (!animationController) {
    animationController = new AnimationController();
  }
  return animationController;
}

export function resetAnimationController(): void {
  if (animationController) {
    animationController.cleanup();
    animationController = null;
  }
}

// React hook for using animation system
export function useAnimationSystem() {
  const [state, setState] = useState<DASHState>("idle");
  const controller = getAnimationController();

  useEffect(() => {
    const unsubscribe = controller.subscribe(setState);
    return unsubscribe;
  }, [controller]);

  return {
    state,
    transitionTo: (newState: DASHState) => controller.transitionTo(newState),
    getCurrentState: () => controller.getCurrentState(),
    getPreviousState: () => controller.getPreviousState(),
    getAnimationConfig: (s: DASHState) => controller.getAnimationConfig(s),
  };
}
