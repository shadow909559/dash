/**
 * ModelSelector — ChatGPT-style model dropdown.
 * Shows grouped models by provider, with "Add custom model" at the bottom.
 */
import React, { useState, useRef, useEffect } from "react";
import { useModelStore } from "@/stores/modelStore";
import {
  ChevronDown,
  Check,
  Zap,
  Globe,
  Cpu,
  Plus,
  X,
  Trash2,
  Eye,
  EyeOff,
} from "lucide-react";

interface ModelSelectorProps {
  compact?: boolean;
}

export const ModelSelector: React.FC<ModelSelectorProps> = ({ compact }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [showAddCustom, setShowAddCustom] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const {
    providers,
    models,
    selectedModelId,
    selectModel,
    addCustomProvider,
    removeCustomProvider,
  } = useModelStore();

  const selectedModel = models.find((m) => m.id === selectedModelId);

  // Close dropdown on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Group models by provider
  const grouped = providers.map((p) => ({
    provider: p,
    models: models.filter((m) => m.providerId === p.id),
  }));

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg
          bg-white/5 hover:bg-white/10 border border-white/10
          text-sm text-white/80 transition-all"
      >
        {selectedModel ? (
          <>
            <span className="text-xs">
              {providers.find((p) => p.id === selectedModel.providerId)?.icon}
            </span>
            <span className="font-medium">{selectedModel.name}</span>
          </>
        ) : (
          <span className="text-white/40">Select model</span>
        )}
        <ChevronDown
          size={14}
          className={`text-white/40 transition-transform ${isOpen ? "rotate-180" : ""}`}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div className="absolute top-full left-0 mt-2 w-80 max-h-96 overflow-y-auto
          bg-[#1a1a2e]/95 backdrop-blur-xl border border-white/10
          rounded-xl shadow-2xl z-50">
          {grouped.map(({ provider, models: providerModels }) =>
            providerModels.length > 0 ? (
              <div key={provider.id}>
                {/* Provider header */}
                <div className="px-3 pt-3 pb-1 text-xs font-semibold text-white/40 uppercase tracking-wider flex items-center gap-2">
                  <span>{provider.icon}</span>
                  <span>{provider.name}</span>
                  {provider.isLocal && (
                    <span className="px-1.5 py-0.5 text-[10px] rounded bg-green-500/20 text-green-400">
                      LOCAL
                    </span>
                  )}
                </div>
                {/* Models */}
                {providerModels.map((model) => (
                  <button
                    key={model.id}
                    onClick={() => {
                      selectModel(model.id);
                      setIsOpen(false);
                    }}
                    className="w-full flex items-center gap-3 px-3 py-2.5
                      hover:bg-white/5 transition-colors text-left"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-white/90 font-medium truncate">
                        {model.name}
                      </div>
                      <div className="text-xs text-white/40 truncate">
                        {model.description}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {model.speed === "fast" && (
                        <Zap size={12} className="text-yellow-400" />
                      )}
                      {model.size && (
                        <span className="text-[10px] text-white/30">{model.size}</span>
                      )}
                      {model.id === selectedModelId && (
                        <Check size={14} className="text-cyan-400" />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            ) : null
          )}

          {/* Divider */}
          <div className="border-t border-white/5 mx-3 my-2" />

          {/* Add custom model */}
          <button
            onClick={() => {
              setShowAddCustom(true);
              setIsOpen(false);
            }}
            className="w-full flex items-center gap-3 px-3 py-2.5
              hover:bg-white/5 transition-colors text-left"
          >
            <div className="w-7 h-7 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Plus size={14} className="text-cyan-400" />
            </div>
            <div>
              <div className="text-sm text-cyan-400 font-medium">Add custom model</div>
              <div className="text-xs text-white/40">
                OpenAI-compatible API with your own key
              </div>
            </div>
          </button>
        </div>
      )}

      {/* Add Custom Model Modal */}
      {showAddCustom && (
        <AddCustomModelModal onClose={() => setShowAddCustom(false)} />
      )}
    </div>
  );
};

// ── Add Custom Model Modal ──────────────────────────────────────────

const AddCustomModelModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const { addCustomProvider } = useModelStore();
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState("https://api.openai.com/v1");
  const [apiKey, setApiKey] = useState("");
  const [modelName, setModelName] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [error, setError] = useState("");
  const [testing, setTesting] = useState(false);

  const handleTestAndAdd = async () => {
    if (!name || !baseUrl || !apiKey || !modelName) {
      setError("All fields are required");
      return;
    }

    setTesting(true);
    setError("");

    try {
      // Test the API connection
      const resp = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${apiKey}`,
        },
        body: JSON.stringify({
          model: modelName,
          messages: [{ role: "user", content: "Hi" }],
          max_tokens: 5,
        }),
      });

      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.error?.message || `HTTP ${resp.status}`);
      }

      // Success — add the provider
      const providerId = `custom-${Date.now()}`;
      addCustomProvider(
        {
          id: providerId,
          name,
          baseUrl,
          apiKey,
          isLocal: false,
          isCustom: true,
          icon: "⚡",
        },
        [
          {
            id: modelName,
            name: modelName,
            provider: name,
            providerId,
            description: `Custom model via ${name}`,
            speed: "medium",
            isLocal: false,
            isCustom: true,
          },
        ]
      );

      onClose();
    } catch (err: any) {
      setError(err.message || "Connection failed");
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div className="bg-[#1a1a2e] border border-white/10 rounded-2xl w-[440px] shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
          <h3 className="text-white font-semibold">Add Custom Model</h3>
          <button onClick={onClose} className="text-white/40 hover:text-white/70">
            <X size={18} />
          </button>
        </div>

        {/* Form */}
        <div className="px-5 py-4 space-y-3">
          <div>
            <label className="text-xs text-white/50 mb-1 block">Provider Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. My OpenAI, Together AI, DeepSeek"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg
                text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50"
            />
          </div>
          <div>
            <label className="text-xs text-white/50 mb-1 block">Base URL</label>
            <input
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.openai.com/v1"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg
                text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50"
            />
          </div>
          <div>
            <label className="text-xs text-white/50 mb-1 block">API Key</label>
            <div className="relative">
              <input
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full px-3 py-2 pr-10 bg-white/5 border border-white/10 rounded-lg
                  text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50"
              />
              <button
                type="button"
                onClick={() => setShowKey(!showKey)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-white/30 hover:text-white/60"
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <label className="text-xs text-white/50 mb-1 block">Model Name</label>
            <input
              value={modelName}
              onChange={(e) => setModelName(e.target.value)}
              placeholder="e.g. gpt-4o, deepseek-chat, claude-3-sonnet"
              className="w-full px-3 py-2 bg-white/5 border border-white/10 rounded-lg
                text-sm text-white placeholder-white/30 focus:outline-none focus:border-cyan-500/50"
            />
          </div>

          {error && (
            <div className="text-xs text-red-400 bg-red-500/10 px-3 py-2 rounded-lg">
              {error}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-5 py-3 border-t border-white/5 flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-white/50 hover:text-white/70 rounded-lg"
          >
            Cancel
          </button>
          <button
            onClick={handleTestAndAdd}
            disabled={testing}
            className="px-4 py-2 text-sm font-medium rounded-lg
              bg-cyan-500/20 text-cyan-400 hover:bg-cyan-500/30
              disabled:opacity-50 transition-all"
          >
            {testing ? "Testing..." : "Test & Add"}
          </button>
        </div>
      </div>
    </div>
  );
};
