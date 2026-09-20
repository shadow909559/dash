// Orb Appearance Store — user-customizable orb palette/speed/wave, persisted
// via zustand persist (same pattern as modelStore) and applied uniformly to
// all three orb surfaces (home Orb, VoicePage orb, JarvisHUD floating orb).

import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface OrbPalettePreset {
  id: string;
  label: string;
  /** Up to 5 stops; PlasmaRing ramps through them pole-to-pole. */
  colors: string[];
}

export const ORB_PALETTES: OrbPalettePreset[] = [
  { id: "state", label: "State-aware (default)", colors: [] },
  { id: "cyan", label: "JARVIS Cyan", colors: ["#3fa9f5", "#1a5276"] },
  { id: "ember", label: "Ember", colors: ["#ff3300", "#ff8c00", "#ffb347"] },
  { id: "violet", label: "Violet Pulse", colors: ["#a855f7", "#4c1d95"] },
  { id: "matrix", label: "Matrix", colors: ["#22ff88", "#0e4d2e"] },
  { id: "gold", label: "Gold Core", colors: ["#facc15", "#b45309"] },
  { id: "ice", label: "Ice", colors: ["#e0f2ff", "#38bdf8", "#0ea5e9"] },
];

export interface OrbAppearance {
  /** "state" = per-state palettes; preset id = that palette for every state;
   *  "custom" = user-picked customColors for every state. */
  paletteId: string;
  /** Custom palette (1–5 hex stops) used when paletteId === "custom". */
  customColors: string[];
  /** Percent multiplier on each surface's per-state speed (100 = default). */
  speedPercent: number;
  /** Percent multiplier on each surface's per-state wave height. */
  wavePercent: number;
}

interface OrbAppearanceActions {
  setPalette: (paletteId: string) => void;
  setCustomColors: (colors: string[]) => void;
  setSpeedPercent: (pct: number) => void;
  setWavePercent: (pct: number) => void;
  resetOrbAppearance: () => void;
}

const defaultAppearance: OrbAppearance = {
  paletteId: "state",
  customColors: ["#3fa9f5", "#a855f7", "#e200ff"],
  speedPercent: 100,
  wavePercent: 100,
};

export const useOrbAppearanceStore = create<
  OrbAppearance & OrbAppearanceActions
>()(
  persist(
    (set) => ({
      ...defaultAppearance,
      setPalette: (paletteId) => set({ paletteId }),
      setCustomColors: (customColors) =>
        set({
          customColors: customColors
            .filter((c) => /^#[0-9a-fA-F]{3,8}$/.test(c.trim()))
            .slice(0, 5),
        }),
      setSpeedPercent: (speedPercent) =>
        set({ speedPercent: Math.max(0, Math.min(200, Math.round(speedPercent))) }),
      setWavePercent: (wavePercent) =>
        set({ wavePercent: Math.max(0, Math.min(200, Math.round(wavePercent))) }),
      resetOrbAppearance: () => set(defaultAppearance),
    }),
    {
      name: "dash.orb.appearance",
      version: 1,
    },
  ),
);

/** Resolve the effective palette for a surface: custom/preset colors, or the
 *  surface's own per-state palette when "state" is selected. */
export function resolveOrbColors(
  appearance: OrbAppearance,
  statePalette: string[],
): string[] {
  if (appearance.paletteId === "state" || appearance.paletteId === "") {
    return statePalette;
  }
  if (appearance.paletteId === "custom") {
    return appearance.customColors.length > 0 ? appearance.customColors : statePalette;
  }
  const preset = ORB_PALETTES.find((p) => p.id === appearance.paletteId);
  return preset && preset.colors.length > 0 ? preset.colors : statePalette;
}

export function resolveOrbSpeed(appearance: OrbAppearance, stateSpeed: number): number {
  return (stateSpeed * appearance.speedPercent) / 100;
}

export function resolveOrbWave(appearance: OrbAppearance, stateWave: number): number {
  return (stateWave * appearance.wavePercent) / 100;
}

/**
 * Keep windows in sync: the Electron floating-orb window is a separate
 * renderer, so a `storage` write from the main window rehydrates this store
 * there live (zustand persist alone does not listen).
 */
export function installOrbAppearanceSync(): () => void {
  const handler = (e: StorageEvent) => {
    if (e.key === "dash.orb.appearance") {
      void useOrbAppearanceStore.persist.rehydrate();
    }
  };
  window.addEventListener("storage", handler);
  return () => window.removeEventListener("storage", handler);
}
