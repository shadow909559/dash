import { create } from "zustand";

type ThemeMode = "light" | "dark";
type AccentColor = "blue" | "purple" | "green" | "orange" | "red" | "pink" | "teal";

interface ThemeState {
  mode: ThemeMode;
  accentColor: AccentColor;
  customAccent: string | null;
  setMode: (mode: ThemeMode) => void;
  toggleMode: () => void;
  setAccentColor: (color: AccentColor) => void;
  setCustomAccent: (color: string | null) => void;
  getAccentCSS: () => string;
}

const ACCENT_MAP: Record<AccentColor, string> = {
  blue: "#3b82f6",
  purple: "#8b5cf6",
  green: "#22c55e",
  orange: "#f97316",
  red: "#ef4444",
  pink: "#ec4899",
  teal: "#14b8a6",
};

export const useThemeStore = create<ThemeState>((set, get) => ({
  mode: (localStorage.getItem("dash_theme_mode") as ThemeMode) || "dark",
  accentColor: (localStorage.getItem("dash_accent_color") as AccentColor) || "purple",
  customAccent: localStorage.getItem("dash_custom_accent"),

  setMode: (mode: ThemeMode) => {
    localStorage.setItem("dash_theme_mode", mode);
    set({ mode });
    document.documentElement.setAttribute("data-theme", mode);
  },

  toggleMode: () => {
    const newMode = get().mode === "dark" ? "light" : "dark";
    get().setMode(newMode);
  },

  setAccentColor: (color: AccentColor) => {
    localStorage.setItem("dash_accent_color", color);
    set({ accentColor: color, customAccent: null });
    localStorage.removeItem("dash_custom_accent");
    const cssColor = ACCENT_MAP[color];
    document.documentElement.style.setProperty("--accent-primary", cssColor);
  },

  setCustomAccent: (color: string | null) => {
    if (color) {
      localStorage.setItem("dash_custom_accent", color);
      set({ customAccent: color });
      document.documentElement.style.setProperty("--accent-primary", color);
    } else {
      set({ customAccent: null });
      const cssColor = ACCENT_MAP[get().accentColor];
      document.documentElement.style.setProperty("--accent-primary", cssColor);
    }
  },

  getAccentCSS: () => {
    const state = get();
    return state.customAccent || ACCENT_MAP[state.accentColor];
  },
}));
