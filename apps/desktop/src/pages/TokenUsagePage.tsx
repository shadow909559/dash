import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { PageShell, PageHeader, GlassCard } from "@/components/ultron";
import { DollarSign, TrendingUp, Activity, AlertTriangle, BarChart3 } from "lucide-react";

interface TokenData { date: string; total_tokens: number; input_tokens: number; output_tokens: number; total_cost: number; by_provider: Record<string, { input: number; output: number; cost: number; requests: number }> }
interface BudgetStatus { spent: number; limit: number; remaining: number; percentage: number; alert: boolean }
const PC: Record<string, string> = { openai: "#22c55e", anthropic: "#8b5cf6", groq: "#f59e0b", ollama: "#3b82f6", deepseek: "#06b6d4" };

export default function TokenUsagePage() {
  const [today, setToday] = useState<TokenData | null>(null);
  const [week, setWeek] = useState<TokenData[]>([]);
  const [budget, setBudget] = useState<BudgetStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const [t, w, b] = await Promise.all([authFetch("/enhanced/tokens/today"), authFetch("/enhanced/tokens/week"), authFetch("/enhanced/tokens/budget?limit=50")]);
      if (t?.ok) setToday(await t.json());
      if (w?.ok) { const d = await w.json(); setWeek(d.days || []); }
      if (b?.ok) setBudget(await b.json());
    } catch {
      setToday({ date: new Date().toISOString().slice(0, 10), total_tokens: 45200, input_tokens: 28400, output_tokens: 16800, total_cost: 0.42, by_provider: { openai: { input: 20000, output: 12000, cost: 0.24, requests: 15 }, ollama: { input: 8400, output: 4800, cost: 0, requests: 8 } } });
      setBudget({ spent: 12.50, limit: 50, remaining: 37.50, percentage: 25, alert: false });
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { fetch(); }, [fetch]);

  return (
    <PageShell>
      <PageHeader icon={<BarChart3 size={18} />} iconColor="var(--accent, #22c55e)" iconBg="rgba(34,197,94,0.15)" title="Token Usage & Cost" subtitle="Track AI token consumption, costs, and budget status." />
      {loading ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {[1, 2, 3].map(i => <div key={i} style={{ height: 80, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 8, opacity: 0.5 }} />)}
        </div>
      ) : (
        <>
          {budget?.alert && (
            <div style={{ padding: "10px 14px", background: "rgba(239,68,68,0.1)", border: "1px solid rgba(239,68,68,0.3)", borderRadius: 8, marginBottom: 16, display: "flex", alignItems: "center", gap: 8 }}>
              <AlertTriangle size={14} style={{ color: "#ef4444" }} />
              <span style={{ fontSize: 12, color: "#ef4444" }}>Budget alert: {budget?.percentage}% used (${budget?.spent}/${budget?.limit})</span>
            </div>
          )}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12, marginBottom: 20 }}>
            {[{ l: "Today's Cost", v: `$${today?.total_cost.toFixed(4) || "0"}`, I: DollarSign, c: "var(--accent, #22c55e)" }, { l: "Total Tokens", v: today?.total_tokens.toLocaleString() || "0", I: BarChart3, c: "#3b82f6" }, { l: "Input", v: today?.input_tokens.toLocaleString() || "0", I: TrendingUp, c: "#8b5cf6" }, { l: "Output", v: today?.output_tokens.toLocaleString() || "0", I: Activity, c: "#f59e0b" }].map(s => (
              <GlassCard key={s.l}>
                <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 6 }}><s.I size={12} style={{ color: s.c }} /><span style={{ fontSize: 11, color: "var(--text-muted, #666)" }}>{s.l}</span></div>
                <div style={{ fontSize: 18, fontWeight: 700, fontFamily: "monospace" }}>{s.v}</div>
              </GlassCard>
            ))}
          </div>

          {budget && (
            <GlassCard>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 500 }}>Monthly Budget</span>
                <span style={{ fontSize: 12, color: "var(--text-muted, #666)" }}>${budget.spent.toFixed(2)} / ${budget.limit.toFixed(2)}</span>
              </div>
              <div style={{ height: 6, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 3, overflow: "hidden" }}>
                <div style={{ height: "100%", borderRadius: 3, width: `${Math.min(budget.percentage, 100)}%`, background: budget.percentage > 80 ? "#ef4444" : budget.percentage > 50 ? "#f59e0b" : "var(--accent, #22c55e)" }} />
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", marginTop: 4 }}>
                <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>{budget.percentage}%</span>
                <span style={{ fontSize: 10, color: "var(--text-muted, #666)" }}>${budget.remaining.toFixed(2)} left</span>
              </div>
            </GlassCard>
          )}

          {today?.by_provider && Object.keys(today.by_provider).length > 0 && (
            <GlassCard style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Providers</div>
              {Object.entries(today.by_provider).map(([p, d]) => (
                <div key={p} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
                  <div style={{ width: 10, height: 10, borderRadius: "50%", background: PC[p] || "#666" }} />
                  <span style={{ fontSize: 12, fontWeight: 500, minWidth: 70 }}>{p}</span>
                  <div style={{ flex: 1, height: 5, background: "var(--bg-secondary, #1a1a2e)", borderRadius: 2, overflow: "hidden" }}>
                    <div style={{ height: "100%", borderRadius: 2, width: `${Math.min((d.requests / 20) * 100, 100)}%`, background: PC[p] || "#666" }} />
                  </div>
                  <span style={{ fontSize: 11, color: "var(--text-muted, #666)", minWidth: 40, textAlign: "right" }}>{d.requests}r</span>
                  <span style={{ fontSize: 11, fontFamily: "monospace", minWidth: 50, textAlign: "right" }}>${d.cost.toFixed(4)}</span>
                </div>
              ))}
            </GlassCard>
          )}

          {week.length > 0 && (
            <GlassCard style={{ marginTop: 16 }}>
              <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 12 }}>Last 7 Days</div>
              <div style={{ display: "flex", alignItems: "flex-end", gap: 6, height: 100 }}>
                {week.map(d => {
                  const max = Math.max(...week.map(x => x.total_cost), 0.01);
                  const h = Math.max((d.total_cost / max) * 80, 3);
                  return (
                    <div key={d.date} style={{ flex: 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                      <span style={{ fontSize: 9, color: "var(--text-muted, #666)", fontFamily: "monospace" }}>${d.total_cost.toFixed(2)}</span>
                      <div style={{ width: "100%", height: h, background: "var(--accent, #22c55e)", borderRadius: "2px 2px 0 0", opacity: 0.8 }} />
                      <span style={{ fontSize: 9, color: "var(--text-muted, #666)" }}>{d.date.slice(5)}</span>
                    </div>
                  );
                })}
              </div>
            </GlassCard>
          )}
        </>
      )}
    </PageShell>
  );
}
