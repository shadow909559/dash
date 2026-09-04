/**
 * ModelSelector — JARVIS-themed model dropdown.
 * Shows grouped models by provider, with "Add custom model" at the bottom.
 * Uses inline styles (no Tailwind dependency).
 */
import React, { useState, useRef, useEffect } from "react";
import { useModelStore } from "@/stores/modelStore";
import {
  ChevronDown,
  Check,
  Zap,
  Plus,
  X,
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

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const grouped = providers.map((p) => ({
    provider: p,
    models: models.filter((m) => m.providerId === p.id),
  }));

  return (
    <div ref={dropdownRef} style={{ position: "relative" }}>
      {/* Trigger button */}
      <button
        onClick={() => setIsOpen(!isOpen)}
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          padding: "6px 12px",
          borderRadius: 8,
          background: "var(--dash-surface)",
          border: "1px solid var(--dash-border)",
          color: "var(--dash-text)",
          fontSize: 13,
          cursor: "pointer",
          transition: "all 150ms ease",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = "var(--dash-border-hover)";
          e.currentTarget.style.background = "var(--dash-surface-hover)";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = "var(--dash-border)";
          e.currentTarget.style.background = "var(--dash-surface)";
        }}
      >
        {selectedModel ? (
          <>
            <span style={{ fontSize: 14 }}>
              {providers.find((p) => p.id === selectedModel.providerId)?.icon}
            </span>
            <span style={{ fontWeight: 500 }}>{selectedModel.name}</span>
          </>
        ) : (
          <span style={{ color: "var(--dash-text-muted)" }}>Select model</span>
        )}
        <ChevronDown
          size={14}
          style={{
            color: "var(--dash-text-muted)",
            transition: "transform 200ms ease",
            transform: isOpen ? "rotate(180deg)" : "rotate(0deg)",
          }}
        />
      </button>

      {/* Dropdown */}
      {isOpen && (
        <div
          style={{
            position: "absolute",
            top: "100%",
            left: 0,
            marginTop: 8,
            width: 320,
            maxHeight: 384,
            overflowY: "auto",
            background: "rgba(8, 12, 20, 0.96)",
            backdropFilter: "blur(16px)",
            border: "1px solid var(--dash-border)",
            borderRadius: 12,
            boxShadow: "0 8px 32px rgba(0, 0, 0, 0.5), 0 0 20px rgba(63, 169, 245, 0.1)",
            zIndex: 50,
          }}
        >
          {grouped.map(({ provider, models: providerModels }) =>
            providerModels.length > 0 ? (
              <div key={provider.id}>
                {/* Provider header */}
                <div
                  style={{
                    padding: "10px 12px 4px",
                    fontSize: 11,
                    fontWeight: 600,
                    color: "var(--dash-text-muted)",
                    textTransform: "uppercase",
                    letterSpacing: "0.08em",
                    display: "flex",
                    alignItems: "center",
                    gap: 6,
                    fontFamily: "'Orbitron', monospace",
                  }}
                >
                  <span>{provider.icon}</span>
                  <span>{provider.name}</span>
                  {provider.isLocal && (
                    <span
                      style={{
                        padding: "1px 6px",
                        fontSize: 9,
                        borderRadius: 4,
                        background: "rgba(34, 197, 94, 0.15)",
                        color: "#22c55e",
                        fontWeight: 600,
                      }}
                    >
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
                    style={{
                      width: "100%",
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 12px",
                      background: model.id === selectedModelId ? "var(--ultron-surface)" : "transparent",
                      border: "none",
                      cursor: "pointer",
                      textAlign: "left",
                      transition: "background 150ms ease",
                      borderLeft: model.id === selectedModelId ? "2px solid var(--dash-accent)" : "2px solid transparent",
                    }}
                    onMouseEnter={(e) => {
                      if (model.id !== selectedModelId) {
                        e.currentTarget.style.background = "rgba(63, 169, 245, 0.06)";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (model.id !== selectedModelId) {
                        e.currentTarget.style.background = "transparent";
                      }
                    }}
                  >
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div
                        style={{
                          fontSize: 13,
                          color: model.id === selectedModelId ? "var(--dash-accent)" : "var(--dash-text)",
                          fontWeight: 500,
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {model.name}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--dash-text-muted)",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {model.description}
                      </div>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                      {model.speed === "fast" && (
                        <Zap size={12} style={{ color: "#eab308" }} />
                      )}
                      {model.size && (
                        <span style={{ fontSize: 10, color: "var(--dash-text-muted)" }}>{model.size}</span>
                      )}
                      {model.id === selectedModelId && (
                        <Check size={14} style={{ color: "var(--dash-accent)" }} />
                      )}
                    </div>
                  </button>
                ))}
              </div>
            ) : null
          )}

          {/* Divider */}
          <div style={{ height: 1, background: "var(--dash-border-subtle)", margin: "4px 12px" }} />

          {/* Add custom model */}
          <button
            onClick={() => {
              setShowAddCustom(true);
              setIsOpen(false);
            }}
            style={{
              width: "100%",
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "8px 12px",
              background: "transparent",
              border: "none",
              cursor: "pointer",
              textAlign: "left",
              transition: "background 150ms ease",
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(63, 169, 245, 0.06)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: 8,
                background: "rgba(63, 169, 245, 0.15)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Plus size={14} style={{ color: "var(--dash-accent)" }} />
            </div>
            <div>
              <div style={{ fontSize: 13, color: "var(--dash-accent)", fontWeight: 500 }}>Add custom model</div>
              <div style={{ fontSize: 11, color: "var(--dash-text-muted)" }}>OpenAI-compatible API with your own key</div>
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

/* ── Add Custom Model Modal ──────────────────────────────────── */

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
      if (!resp.ok) throw new Error(`API returned ${resp.status}`);
      const providerId = `custom-${Date.now()}`;
      addCustomProvider(
        {
          id: providerId,
          name,
          baseUrl,
          apiKey,
          isLocal: false,
          isCustom: true,
          icon: "🔌",
        },
        [
          {
            id: `${providerId}:${modelName}`,
            name: modelName,
            provider: name,
            providerId,
            description: `Custom model via ${name}`,
            speed: "medium" as const,
            isLocal: false,
            isCustom: true,
          },
        ],
      );
      onClose();
    } catch (err: any) {
      setError(err.message || "Connection failed");
    } finally {
      setTesting(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "8px 12px",
    borderRadius: 8,
    background: "var(--dash-surface)",
    border: "1px solid var(--dash-border)",
    color: "var(--dash-text)",
    fontSize: 13,
    outline: "none",
    fontFamily: "'Inter', sans-serif",
  };

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        background: "rgba(0, 0, 0, 0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 100,
      }}
      onClick={onClose}
    >
      <div
        style={{
          width: 400,
          padding: 24,
          borderRadius: 16,
          background: "var(--dash-bg-subtle)",
          border: "1px solid var(--dash-border)",
          boxShadow: "0 16px 48px rgba(0, 0, 0, 0.5), 0 0 30px rgba(63, 169, 245, 0.1)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--dash-text)", fontFamily: "'Orbitron', monospace" }}>
            Add Custom Model
          </h3>
          <button onClick={onClose} style={{ background: "none", border: "none", color: "var(--dash-text-muted)", cursor: "pointer" }}>
            <X size={18} />
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <div>
            <label style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4, display: "block", fontFamily: "'Orbitron', monospace", letterSpacing: "0.05em" }}>NAME</label>
            <input style={inputStyle} value={name} onChange={(e) => setName(e.target.value)} placeholder="My Custom Model" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4, display: "block", fontFamily: "'Orbitron', monospace", letterSpacing: "0.05em" }}>API BASE URL</label>
            <input style={inputStyle} value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} placeholder="https://api.openai.com/v1" />
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4, display: "block", fontFamily: "'Orbitron', monospace", letterSpacing: "0.05em" }}>API KEY</label>
            <div style={{ position: "relative" }}>
              <input
                style={{ ...inputStyle, paddingRight: 36 }}
                type={showKey ? "text" : "password"}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
              />
              <button
                onClick={() => setShowKey(!showKey)}
                style={{ position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)", background: "none", border: "none", color: "var(--dash-text-muted)", cursor: "pointer" }}
              >
                {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </div>
          <div>
            <label style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 4, display: "block", fontFamily: "'Orbitron', monospace", letterSpacing: "0.05em" }}>MODEL NAME</label>
            <input style={inputStyle} value={modelName} onChange={(e) => setModelName(e.target.value)} placeholder="gpt-4, claude-3, etc." />
          </div>

          {error && (
            <div style={{ fontSize: 12, color: "#ef4444", padding: "6px 10px", borderRadius: 6, background: "rgba(239, 68, 68, 0.1)" }}>
              {error}
            </div>
          )}

          <button
            onClick={handleTestAndAdd}
            disabled={testing}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              background: testing ? "var(--dash-surface)" : "linear-gradient(135deg, #3fa9f5, #1a5276)",
              border: "none",
              color: "#fff",
              fontSize: 13,
              fontWeight: 600,
              cursor: testing ? "wait" : "pointer",
              fontFamily: "'Orbitron', monospace",
              letterSpacing: "0.05em",
              boxShadow: testing ? "none" : "0 0 15px rgba(63, 169, 245, 0.3)",
            }}
          >
            {testing ? "Testing connection..." : "Test & Add Model"}
          </button>
        </div>
      </div>
    </div>
  );
};
