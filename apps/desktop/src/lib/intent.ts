export type CommandIntent =
  | { type: "research"; query: string }
  | { type: "system" }
  | { type: "files"; query?: string }
  | { type: "coding" }
  | { type: "memory" }
  | { type: "chat" };

export function detectIntent(text: string): CommandIntent {
  const t = text.trim();
  const lower = t.toLowerCase();

  if (
    /\b(research|look up|search (the )?web|latest developments|investigate|find sources)\b/.test(lower)
  ) {
    const query = t.replace(/^(please\s+)?(research|look up|search (the )?web for|investigate)\s+/i, "").trim() || t;
    return { type: "research", query };
  }

  if (/\b(system status|system monitor|show (cpu|ram|stats|telemetry)|how('s| is) (the )?system)\b/.test(lower)) {
    return { type: "system" };
  }

  if (/\b(open files|file explorer|show files|browse files)\b/.test(lower)) {
    return { type: "files" };
  }

  if (/\b(code|coding|write a (function|script|program)|debug this)\b/.test(lower)) {
    return { type: "coding" };
  }

  if (/\b(memory|what do you remember|recall)\b/.test(lower)) {
    return { type: "memory" };
  }

  return { type: "chat" };
}
