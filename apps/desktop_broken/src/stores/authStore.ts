import { create } from "zustand";
import { auth } from "@/lib/api";

interface User {
  id: string;
  email: string;
  name?: string;
}

interface AuthState {
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name?: string) => Promise<void>;
  logout: () => void;
  checkAuth: () => Promise<void>;
  clearError: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,

  login: async (email: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const result = await auth.login(email, password);
      localStorage.setItem("dash_access_token", result.access_token);
      localStorage.setItem("dash_refresh_token", result.refresh_token);
      const user = await auth.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
      throw err;
    }
  },

  register: async (email: string, password: string, username?: string) => {
    set({ isLoading: true, error: null });
    try {
      await auth.register(email, password, username);
      set({ isLoading: false });
    } catch (err) {
      set({ error: (err as Error).message, isLoading: false });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("dash_access_token");
    localStorage.removeItem("dash_refresh_token");
    try {
      const { resetWsClient } = require("@/lib/wsClient");
      resetWsClient();
    } catch {}
    set({ user: null, isAuthenticated: false, isLoading: false });
  },

  checkAuth: async () => {
    const token = localStorage.getItem("dash_access_token");
    if (!token) {
      set({ isLoading: false });
      return;
    }
    try {
      const user = await auth.me();
      set({ user, isAuthenticated: true, isLoading: false });
    } catch {
      localStorage.removeItem("dash_access_token");
      localStorage.removeItem("dash_refresh_token");
      set({ isLoading: false });
    }
  },

  clearError: () => set({ error: null }),
}));