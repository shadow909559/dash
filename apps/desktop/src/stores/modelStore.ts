/**
 * Model Registry Store — manages all AI providers, models, and custom API keys.
 *
 * Built-in providers come pre-configured. Users can add custom OpenAI-compatible
 * providers with their own API keys and model names.
 */
import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface AIModel {
  id: string;
  name: string;
  provider: string;
  providerId: string;
  description: string;
  speed: "fast" | "medium" | "slow";
  size?: string; // e.g. "1B", "7B", "Flash"
  isLocal: boolean;
  isCustom?: boolean;
}

export interface AIProvider {
  id: string;
  name: string;
  baseUrl: string;
  apiKey: string;
  isLocal: boolean;
  isCustom?: boolean;
  icon: string;
}

interface ModelState {
  providers: AIProvider[];
  models: AIModel[];
  selectedModelId: string;
  customProviders: AIProvider[];

  selectModel: (modelId: string) => void;
  addCustomProvider: (provider: AIProvider, models: AIModel[]) => void;
  removeCustomProvider: (providerId: string) => void;
  updateCustomProvider: (providerId: string, updates: Partial<AIProvider>) => void;
  getSelectedModel: () => AIModel | undefined;
  getModelsByProvider: (providerId: string) => AIModel[];
}

const BUILTIN_PROVIDERS: AIProvider[] = [
  {
    id: "gemini",
    name: "Google Gemini",
    baseUrl: "https://generativelanguage.googleapis.com/v1beta/openai",
    apiKey: "",
    isLocal: false,
    icon: "✦",
  },
  {
    id: "grok",
    name: "xAI Grok",
    baseUrl: "https://api.x.ai/v1",
    apiKey: "",
    isLocal: false,
    icon: "✖",
  },
  {
    id: "groq",
    name: "Groq (Ultra-Fast)",
    baseUrl: "https://api.groq.com/openai/v1",
    apiKey: "",
    isLocal: false,
    icon: "⚡",
  },
  {
    id: "ollama",
    name: "Ollama (Local)",
    baseUrl: "http://127.0.0.1:11434",
    apiKey: "",
    isLocal: true,
    icon: "🦙",
  },
];

const BUILTIN_MODELS: AIModel[] = [
  // Gemini
  {
    id: "gemini-3.6-flash",
    name: "Gemini 3.6 Flash",
    provider: "Google Gemini",
    providerId: "gemini",
    description: "Fastest Gemini model — great for quick tasks",
    speed: "fast",
    size: "Flash",
    isLocal: false,
  },
  {
    id: "gemini-2.5-pro",
    name: "Gemini 2.5 Pro",
    provider: "Google Gemini",
    providerId: "gemini",
    description: "Most capable Gemini — best reasoning",
    speed: "medium",
    size: "Pro",
    isLocal: false,
  },
  // Grok
  {
    id: "grok-3",
    name: "Grok 3",
    provider: "xAI Grok",
    providerId: "grok",
    description: "xAI's latest — real-time info, witty",
    speed: "medium",
    isLocal: false,
  },
  {
    id: "grok-3-mini",
    name: "Grok 3 Mini",
    provider: "xAI Grok",
    providerId: "grok",
    description: "Faster Grok — good for quick tasks",
    speed: "fast",
    isLocal: false,
  },
  // Groq
  {
    id: "llama-3.3-70b-versatile",
    name: "Llama 3.3 70B (Groq)",
    provider: "Groq (Ultra-Fast)",
    providerId: "groq",
    description: "Ultra-fast 70B — near-instant responses",
    speed: "fast",
    size: "70B",
    isLocal: false,
  },
  {
    id: "llama-3.1-8b-instant",
    name: "Llama 3.1 8B Instant (Groq)",
    provider: "Groq (Ultra-Fast)",
    providerId: "groq",
    description: "Fast 8B — quick tasks, low latency",
    speed: "fast",
    size: "8B",
    isLocal: false,
  },
  {
    id: "mixtral-8x7b-32768",
    name: "Mixtral 8x7B (Groq)",
    provider: "Groq (Ultra-Fast)",
    providerId: "groq",
    description: "Mixture of experts — balanced speed/quality",
    speed: "fast",
    size: "8x7B",
    isLocal: false,
  },
  // Ollama (local)
  {
    id: "llama3.2:1b",
    name: "Llama 3.2 1B",
    provider: "Ollama (Local)",
    providerId: "ollama",
    description: "Ultra-fast local model — basic tasks",
    speed: "fast",
    size: "1B",
    isLocal: true,
  },
  {
    id: "llama3.2:3b",
    name: "Llama 3.2 3B",
    provider: "Ollama (Local)",
    providerId: "ollama",
    description: "Good balance of speed and quality",
    speed: "medium",
    size: "3B",
    isLocal: true,
  },
  {
    id: "qwen2.5-coder:7b",
    name: "Qwen 2.5 Coder 7B",
    provider: "Ollama (Local)",
    providerId: "ollama",
    description: "Specialized for code generation",
    speed: "slow",
    size: "7B",
    isLocal: true,
  },
];

export const useModelStore = create<ModelState>()(
  persist(
    (set, get) => ({
      providers: BUILTIN_PROVIDERS,
      models: BUILTIN_MODELS,
      selectedModelId: "gemini-3.6-flash",
      customProviders: [],

      selectModel: (modelId: string) => {
        set({ selectedModelId: modelId });
        // Notify backend of model change
        const model = get().models.find((m) => m.id === modelId);
        if (model) {
          fetch("http://127.0.0.1:8000/api/ai/model", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              provider: model.providerId,
              model: model.id,
              baseUrl: get().providers.find((p) => p.id === model.providerId)?.baseUrl,
              apiKey: get().providers.find((p) => p.id === model.providerId)?.apiKey,
            }),
          }).catch(() => {});
        }
      },

      addCustomProvider: (provider: AIProvider, models: AIModel[]) => {
        set((state) => ({
          customProviders: [...state.customProviders, provider],
          providers: [...state.providers, provider],
          models: [...state.models, ...models],
        }));
      },

      removeCustomProvider: (providerId: string) => {
        set((state) => ({
          customProviders: state.customProviders.filter((p) => p.id !== providerId),
          providers: state.providers.filter((p) => p.id !== providerId),
          models: state.models.filter((m) => m.providerId !== providerId),
        }));
      },

      updateCustomProvider: (providerId: string, updates: Partial<AIProvider>) => {
        set((state) => ({
          providers: state.providers.map((p) =>
            p.id === providerId ? { ...p, ...updates } : p
          ),
          customProviders: state.customProviders.map((p) =>
            p.id === providerId ? { ...p, ...updates } : p
          ),
        }));
      },

      getSelectedModel: () => {
        const state = get();
        return state.models.find((m) => m.id === state.selectedModelId);
      },

      getModelsByProvider: (providerId: string) => {
        return get().models.filter((m) => m.providerId === providerId);
      },
    }),
    {
      name: "dash-model-store",
      partialize: (state) => ({
        selectedModelId: state.selectedModelId,
        customProviders: state.customProviders,
        // Merge custom models into the models list on rehydration
      }),
    }
  )
);
