import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { api } from "../api/client";
import {
  Badge,
  Button,
  EyebrowLabel,
  HairlineRule,
  Input,
  PageSpinner,
} from "../components/ui";

type Provider = {
  id: string;
  name: string;
  base_url: string;
  models: string[];
  enabled: boolean;
};

type Role = "writer" | "reviewer" | "lite";

type Binding = {
  role: Role;
  provider_id: string;
  model: string;
};

type ProviderFormState = {
  name: string;
  base_url: string;
  api_key: string;
  models: string;
};

const EMPTY_PROVIDER_FORM: ProviderFormState = {
  name: "",
  base_url: "",
  api_key: "",
  models: "",
};

const ROLE_LABELS: Record<Role, string> = {
  writer: "改写",
  reviewer: "审核",
  lite: "轻量",
};

const ROLE_DESCRIPTIONS: Record<Role, string> = {
  writer: "负责文章改写的主力模型",
  reviewer: "负责内容审核与评分",
  lite: "轻量任务（如标签生成）",
};

// ---- Provider form ----

interface ProviderFormProps {
  onSuccess: () => void;
}

function ProviderForm({ onSuccess }: ProviderFormProps) {
  const [form, setForm] = useState<ProviderFormState>(EMPTY_PROVIDER_FORM);
  const [open, setOpen] = useState(false);

  function set(field: keyof ProviderFormState, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  const create = useMutation({
    mutationFn: async () =>
      api.post("/ai-providers", {
        ...form,
        models: form.models
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      setForm(EMPTY_PROVIDER_FORM);
      setOpen(false);
      onSuccess();
    },
  });

  if (!open) {
    return (
      <Button variant="secondary" size="sm" onClick={() => setOpen(true)}>
        添加 Provider
      </Button>
    );
  }

  return (
    <div
      className="surface-paper"
      style={{
        padding: "var(--space-5)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-4)",
      }}
    >
      <p
        style={{
          fontSize: "var(--text-sm)",
          fontWeight: "var(--weight-semi)",
          color: "var(--color-ink)",
          margin: 0,
        }}
      >
        新增 AI Provider
      </p>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
        <Input
          label="名称"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          placeholder="例：Kimi"
          required
        />
        <Input
          label="Base URL"
          value={form.base_url}
          onChange={(e) => set("base_url", e.target.value)}
          placeholder="https://api.moonshot.cn/v1"
          style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}
        />
      </div>

      <Input
        label="API Key"
        type="password"
        value={form.api_key}
        onChange={(e) => set("api_key", e.target.value)}
        placeholder="sk-..."
        style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}
      />

      <Input
        label="模型列表"
        value={form.models}
        onChange={(e) => set("models", e.target.value)}
        placeholder="moonshot-v1-8k, moonshot-v1-32k"
        hint="逗号分隔"
      />

      {create.isError && (
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", margin: 0 }}>
          添加失败，请检查填写内容后重试
        </p>
      )}

      <div style={{ display: "flex", gap: "var(--space-2)" }}>
        <Button
          onClick={() => create.mutate()}
          loading={create.isPending}
          disabled={!form.name || !form.base_url || !form.api_key}
        >
          保存
        </Button>
        <Button variant="ghost" onClick={() => setOpen(false)} disabled={create.isPending}>
          取消
        </Button>
      </div>
    </div>
  );
}

// ---- Role binding row ----

interface RoleRowProps {
  role: Role;
  providers: Provider[];
  current: Binding | undefined;
  onSave: (b: Binding) => void;
  isSaving: boolean;
}

function RoleRow({ role, providers, current, onSave, isSaving }: RoleRowProps) {
  const [providerId, setProviderId] = useState(current?.provider_id ?? "");
  const [model, setModel] = useState(current?.model ?? "");

  const selectedProvider = providers.find((p) => p.id === providerId);

  const selectStyle: React.CSSProperties = {
    padding: "var(--space-2) var(--space-3)",
    fontSize: "var(--text-sm)",
    color: "var(--color-ink)",
    backgroundColor: "var(--color-white)",
    border: "1px solid var(--color-surface-3)",
    borderRadius: "var(--radius-md)",
    outline: "none",
    cursor: "pointer",
    width: "100%",
  };

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "140px 1fr 1fr auto",
        gap: "var(--space-3)",
        alignItems: "end",
        padding: "var(--space-4) var(--space-2)",
        borderBottom: "1px solid var(--color-surface-3)",
      }}
    >
      {/* Role label */}
      <div>
        <p
          style={{
            fontSize: "var(--text-sm)",
            fontWeight: "var(--weight-semi)",
            color: "var(--color-ink)",
            margin: "0 0 var(--space-1) 0",
          }}
        >
          {ROLE_LABELS[role]}
        </p>
        <p
          style={{
            fontSize: "var(--text-xs)",
            color: "var(--color-ink-3)",
            margin: 0,
            lineHeight: "var(--leading-snug)",
          }}
        >
          {ROLE_DESCRIPTIONS[role]}
        </p>
      </div>

      {/* Provider select */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label className="field-label" style={{ marginBottom: 0 }}>Provider</label>
        <select
          value={providerId}
          onChange={(e) => {
            setProviderId(e.target.value);
            setModel("");
          }}
          style={selectStyle}
        >
          <option value="">— 选择 —</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
      </div>

      {/* Model select/input */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label className="field-label" style={{ marginBottom: 0 }}>模型</label>
        {selectedProvider && selectedProvider.models.length > 0 ? (
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={{ ...selectStyle, fontFamily: "var(--font-mono)" }}
          >
            <option value="">— 选择模型 —</option>
            {selectedProvider.models.map((m) => (
              <option key={m} value={m}>{m}</option>
            ))}
          </select>
        ) : (
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="模型 ID"
            className="input-base input-mono"
          />
        )}
      </div>

      <Button
        size="sm"
        onClick={() => onSave({ role, provider_id: providerId, model })}
        disabled={!providerId || !model}
        loading={isSaving}
      >
        保存
      </Button>
    </div>
  );
}

// ---- Usage dashboard ----

type DailyUsage = {
  day: string;
  prompt_tokens: number;
  completion_tokens: number;
  cost_estimate: number;
  by_role?: Record<string, number>;
};

type RoleUsage = {
  role: string | null;
  provider: string | null;
  model: string;
  calls: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_estimate: number;
};

type UsageSummary = {
  days: number;
  daily: DailyUsage[];
  by_role: RoleUsage[];
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_cost: number;
};

const ROLE_STACK_ORDER = ["writer", "reviewer", "lite", "unknown"] as const;

const ROLE_COLORS: Record<string, string> = {
  writer: "var(--color-ink)",
  reviewer: "var(--color-ink-3)",
  lite: "var(--color-ink-4)",
  unknown: "var(--color-surface-4)",
};

const ROLE_DASH_LABELS: Record<string, string> = {
  writer: "改写",
  reviewer: "审核",
  lite: "轻量",
  unknown: "未知",
};

function formatCost(c: number): string {
  if (c >= 10) return `$${c.toFixed(2)}`;
  return `$${c.toFixed(4)}`;
}

function formatDelta(ratio: number | null): { text: string; color: string } {
  if (ratio === null) {
    return { text: "无对比基线", color: "var(--color-ink-3)" };
  }
  const pct = ratio * 100;
  const sign = pct >= 0 ? "+" : "";
  const text = `${sign}${pct.toFixed(1)}%`;
  const color =
    pct > 0
      ? "var(--color-failed-fg)"
      : pct < 0
      ? "var(--color-done-fg)"
      : "var(--color-ink-3)";
  return { text, color };
}

function shortDay(iso: string): string {
  return iso.length >= 10 ? iso.slice(5) : iso;
}

interface ChartHover {
  day: string;
  total: number;
  byRole: Record<string, number>;
  index: number;
  totalDays: number;
}

function UsageDashboard() {
  const usage = useQuery({
    queryKey: ["usage-summary", 60],
    queryFn: async () =>
      (await api.get<UsageSummary>("/usage/summary?days=60")).data,
  });

  const [hover, setHover] = useState<ChartHover | null>(null);

  const days30 = useMemo<string[]>(() => {
    const arr: string[] = [];
    const now = new Date();
    for (let i = 29; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      arr.push(d.toISOString().slice(0, 10));
    }
    return arr;
  }, []);

  const stats = useMemo(() => {
    if (!usage.data) return null;
    try {
      const daily = usage.data.daily ?? [];
      const byRole = usage.data.by_role ?? [];
      const dailyMap = new Map(daily.map((d) => [d.day, d]));
      const cutoff = days30[0];
      let recentCost = 0;
      let priorCost = 0;
      let recentPrompt = 0;
      let recentCompletion = 0;
      for (const d of daily) {
        if (d.day >= cutoff) {
          recentCost += d.cost_estimate;
          recentPrompt += d.prompt_tokens;
          recentCompletion += d.completion_tokens;
        } else {
          priorCost += d.cost_estimate;
        }
      }
      const delta = priorCost === 0 ? null : (recentCost - priorCost) / priorCost;

      const seenRoles = new Set<string>();
      for (const day of days30) {
        const entry = dailyMap.get(day);
        if (!entry?.by_role) continue;
        for (const role of Object.keys(entry.by_role)) seenRoles.add(role);
      }
      const orderedRoles = [
        ...ROLE_STACK_ORDER.filter((r) => seenRoles.has(r)),
        ...[...seenRoles].filter(
          (r) => !ROLE_STACK_ORDER.includes(r as (typeof ROLE_STACK_ORDER)[number])
        ),
      ];

      const maxCost = days30.reduce((m, day) => {
        const entry = dailyMap.get(day);
        return entry ? Math.max(m, entry.cost_estimate) : m;
      }, 0);

      return { dailyMap, recentCost, priorCost, recentPrompt, recentCompletion, delta, orderedRoles, maxCost, daily, byRole };
    } catch {
      return null;
    }
  }, [usage.data, days30]);

  if (!usage.data) return null;

  // Data exists but is empty — show placeholder instead of crashing
  if (!stats || (stats.daily.length === 0)) {
    return (
      <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <h2 className="text-section-title">AI 用量</h2>
        <p className="text-page-subtitle">暂无 AI 用量数据 — 完成首次改写后将出现统计</p>
      </section>
    );
  }
  const u = usage.data;
  const delta = formatDelta(stats.delta);

  return (
    <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
      <h2
        style={{
          fontSize: "var(--text-lg)",
          fontWeight: "var(--weight-semi)",
          color: "var(--color-ink)",
          letterSpacing: "-0.02em",
          margin: 0,
        }}
      >
        AI 用量
      </h2>

      {/* Hero number block */}
      <div>
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "3fr 2fr",
            gap: "var(--space-6)",
            alignItems: "end",
          }}
        >
          <div>
            <EyebrowLabel>近 30 天总成本（估算）</EyebrowLabel>
            <p
              style={{
                margin: "var(--space-2) 0 0 0",
                fontSize: "calc(var(--text-3xl) * 1.6)",
                fontWeight: "var(--weight-semi)",
                color: "var(--color-ink)",
                letterSpacing: "-0.04em",
                lineHeight: 1,
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {formatCost(stats.recentCost)}
            </p>
            <p
              style={{
                margin: "var(--space-2) 0 0 0",
                fontSize: "var(--text-xs)",
                fontFamily: "var(--font-mono)",
                color: "var(--color-ink-3)",
                letterSpacing: "0.02em",
              }}
            >
              vs 上 30 天{" "}
              <span style={{ color: delta.color, fontWeight: "var(--weight-medium)" }}>
                {delta.text}
              </span>
            </p>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {[
              { label: "Prompt tokens", value: stats.recentPrompt },
              { label: "Completion tokens", value: stats.recentCompletion },
            ].map(({ label, value }) => (
              <div key={label}>
                <EyebrowLabel tone="subtle">{label}</EyebrowLabel>
                <p
                  style={{
                    margin: "var(--space-1) 0 0 0",
                    fontSize: "var(--text-xl)",
                    fontWeight: "var(--weight-semi)",
                    color: "var(--color-ink)",
                    letterSpacing: "-0.02em",
                    lineHeight: 1,
                    fontFamily: "var(--font-mono)",
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  {value.toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </div>
        <HairlineRule style={{ marginTop: "var(--space-5)" }} />
      </div>

      {/* Stacked bar chart */}
      <div style={{ position: "relative" }}>
        <div
          style={{
            display: "flex",
            alignItems: "baseline",
            justifyContent: "space-between",
            marginBottom: "var(--space-3)",
          }}
        >
          <EyebrowLabel>每日成本 · 按角色</EyebrowLabel>
          <div style={{ display: "flex", gap: "var(--space-3)" }}>
            {stats.orderedRoles.map((role) => (
              <div key={role} style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                <span
                  aria-hidden="true"
                  style={{
                    width: "8px",
                    height: "8px",
                    backgroundColor: ROLE_COLORS[role] ?? "var(--color-surface-4)",
                  }}
                />
                <span
                  style={{
                    fontSize: "var(--text-xs)",
                    color: "var(--color-ink-3)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {ROLE_DASH_LABELS[role] ?? role}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div
          style={{
            position: "relative",
            display: "flex",
            alignItems: "flex-end",
            gap: "2px",
            height: "112px",
          }}
          onMouseLeave={() => setHover(null)}
        >
          {days30.map((day, index) => {
            const entry = stats.dailyMap.get(day);
            const total = entry?.cost_estimate ?? 0;
            const byRole = entry?.by_role ?? {};
            const heightPct = stats.maxCost > 0 ? (total / stats.maxCost) * 100 : 0;
            const isHover = hover?.day === day;

            return (
              <div
                key={day}
                onMouseEnter={() => setHover({ day, total, byRole, index, totalDays: days30.length })}
                style={{
                  flex: 1,
                  minWidth: 0,
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "flex-end",
                  position: "relative",
                }}
              >
                {total > 0 ? (
                  <div
                    style={{
                      height: `${Math.max(2, heightPct)}%`,
                      display: "flex",
                      flexDirection: "column-reverse",
                      opacity: isHover || !hover ? 1 : 0.45,
                      transition: "opacity var(--dur-fast)",
                    }}
                  >
                    {stats.orderedRoles.map((role) => {
                      const cost = byRole[role] ?? 0;
                      if (cost <= 0) return null;
                      const segPct = (cost / total) * 100;
                      return (
                        <div
                          key={role}
                          style={{
                            height: `${segPct}%`,
                            backgroundColor: ROLE_COLORS[role] ?? "var(--color-surface-4)",
                          }}
                        />
                      );
                    })}
                  </div>
                ) : (
                  <div
                    style={{
                      height: "1px",
                      backgroundColor: "var(--color-surface-3)",
                      opacity: !hover || isHover ? 1 : 0.45,
                      transition: "opacity var(--dur-fast)",
                    }}
                  />
                )}
              </div>
            );
          })}

          {/* Hover popover */}
          {hover && (
            <div
              role="tooltip"
              style={{
                position: "absolute",
                bottom: "calc(100% + 8px)",
                left: `${(hover.index / Math.max(1, hover.totalDays - 1)) * 100}%`,
                transform: `translateX(${
                  hover.index < 4 ? "0%" : hover.index > hover.totalDays - 5 ? "-100%" : "-50%"
                })`,
                backgroundColor: "var(--color-ink)",
                color: "var(--color-accent-fg)",
                padding: "var(--space-3) var(--space-4)",
                borderRadius: "var(--radius-md)",
                fontSize: "var(--text-xs)",
                fontFamily: "var(--font-mono)",
                fontVariantNumeric: "tabular-nums",
                whiteSpace: "nowrap",
                boxShadow: "var(--shadow-lg)",
                zIndex: 5,
                pointerEvents: "none",
                lineHeight: "var(--leading-snug)",
              }}
            >
              <div style={{ fontWeight: "var(--weight-medium)", marginBottom: "var(--space-1)", letterSpacing: "0.04em" }}>
                {hover.day}
              </div>
              {stats.orderedRoles.map((role) => {
                const c = hover.byRole[role] ?? 0;
                if (c <= 0) return null;
                return (
                  <div
                    key={role}
                    style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", justifyContent: "space-between" }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: "var(--space-1)" }}>
                      <span aria-hidden="true" style={{ width: "6px", height: "6px", backgroundColor: ROLE_COLORS[role] ?? "var(--color-surface-4)" }} />
                      <span style={{ opacity: 0.7 }}>{ROLE_DASH_LABELS[role] ?? role}</span>
                    </span>
                    <span>{formatCost(c)}</span>
                  </div>
                );
              })}
              {hover.total === 0 && <div style={{ opacity: 0.6 }}>无调用</div>}
              {hover.total > 0 && (
                <div
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    marginTop: "var(--space-1)",
                    paddingTop: "var(--space-1)",
                    borderTop: "1px solid rgba(255,255,255,0.15)",
                  }}
                >
                  <span style={{ opacity: 0.7 }}>total</span>
                  <span style={{ fontWeight: "var(--weight-medium)" }}>{formatCost(hover.total)}</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* X-axis */}
        <div style={{ display: "flex", gap: "2px", marginTop: "var(--space-2)" }}>
          {days30.map((day, i) => (
            <div
              key={day}
              style={{
                flex: 1,
                minWidth: 0,
                textAlign: "center",
                fontSize: "var(--text-xs)",
                fontFamily: "var(--font-mono)",
                color: "var(--color-ink-4)",
                opacity: i % 7 === 0 || i === days30.length - 1 ? 1 : 0,
              }}
            >
              {shortDay(day)}
            </div>
          ))}
        </div>

        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "baseline",
            marginTop: "var(--space-3)",
            color: "var(--color-ink-3)",
            fontSize: "var(--text-xs)",
            fontFamily: "var(--font-mono)",
          }}
        >
          <span>{days30[0]} → {days30[days30.length - 1]}</span>
          <span style={{ color: "var(--color-ink)", letterSpacing: "0.02em", fontWeight: "var(--weight-medium)" }}>
            total · {formatCost(stats.recentCost)}
          </span>
        </div>
      </div>

      {/* By-role table */}
      {(u.by_role ?? []).length > 0 && (
        <div
          style={{
            backgroundColor: "var(--color-white)",
            border: "1px solid var(--color-surface-3)",
            borderRadius: "var(--radius-lg)",
            overflow: "hidden",
          }}
        >
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
            <thead>
              <tr style={{ backgroundColor: "var(--color-surface-2)" }}>
                {["角色", "Provider / 模型", "调用次数", "Tokens", "成本"].map((h, i) => (
                  <th
                    key={h}
                    style={{
                      padding: "var(--space-3) var(--space-4)",
                      textAlign: i >= 2 ? "right" : "left",
                      fontSize: "var(--text-xs)",
                      fontWeight: "var(--weight-semi)",
                      color: "var(--color-ink-3)",
                      textTransform: "uppercase",
                      letterSpacing: "0.05em",
                      borderBottom: "1px solid var(--color-surface-3)",
                    }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(u.by_role ?? []).map((r, i) => {
                const roleKey = r.role ?? "unknown";
                const swatchColor = ROLE_COLORS[roleKey] ?? "var(--color-surface-4)";
                const dashLabel = ROLE_DASH_LABELS[roleKey] ?? roleKey;
                return (
                  <tr
                    key={i}
                    style={{
                      borderTop: i > 0 ? "1px solid var(--color-surface-2)" : "none",
                      transition: "background-color var(--dur-fast)",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "var(--color-surface-2)"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = ""; }}
                  >
                    <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-2)" }}>
                        <span aria-hidden="true" style={{ width: "8px", height: "8px", backgroundColor: swatchColor, flexShrink: 0 }} />
                        <EyebrowLabel as="span">{dashLabel}</EyebrowLabel>
                      </span>
                    </td>
                    <td style={{ padding: "var(--space-3) var(--space-4)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-ink-2)" }}>
                      {r.provider ?? "—"} / {r.model}
                    </td>
                    <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: "var(--text-xs)", color: "var(--color-ink-2)" }}>
                      {r.calls}
                    </td>
                    <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: "var(--text-xs)", color: "var(--color-ink-2)" }}>
                      {(r.prompt_tokens + r.completion_tokens).toLocaleString()}
                    </td>
                    <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", fontVariantNumeric: "tabular-nums", fontSize: "var(--text-xs)", color: "var(--color-ink)", fontWeight: "var(--weight-medium)" }}>
                      {formatCost(r.cost_estimate)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// ---- Main page ----

export default function Settings() {
  const qc = useQueryClient();

  const providers = useQuery({
    queryKey: ["providers"],
    queryFn: async () => (await api.get<Provider[]>("/ai-providers")).data,
  });

  const bindings = useQuery({
    queryKey: ["bindings"],
    queryFn: async () =>
      (await api.get<Binding[]>("/ai-providers/role-bindings")).data,
  });

  const [savingRole, setSavingRole] = useState<Role | null>(null);

  const upsertBinding = useMutation({
    mutationFn: async (b: Binding) => {
      setSavingRole(b.role);
      return api.put("/ai-providers/role-bindings", b);
    },
    onSuccess: () => {
      setSavingRole(null);
      qc.invalidateQueries({ queryKey: ["bindings"] });
    },
    onError: () => setSavingRole(null),
  });

  if (providers.isLoading) return <PageSpinner />;

  return (
    <div className="page-shell page-shell-narrow" style={{ display: "flex", flexDirection: "column", gap: "var(--space-10)" }}>
      {/* Page header */}
      <div className="page-header" style={{ marginBottom: 0 }}>
        <div className="page-header-meta">
          <h1 className="text-page-title">设置</h1>
          <p className="text-page-subtitle">AI 服务商配置 · 角色绑定 · 用量看板</p>
        </div>
      </div>

      {/* AI Providers */}
      <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
        <h2
          style={{
            fontSize: "var(--text-lg)",
            fontWeight: "var(--weight-semi)",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          AI 服务商
        </h2>

        {providers.data && providers.data.length > 0 && (
          <div style={{ display: "flex", flexDirection: "column" }}>
            {providers.data.map((p, i) => (
              <div
                key={p.id}
                style={{
                  display: "grid",
                  gridTemplateColumns: "auto 1fr auto",
                  alignItems: "center",
                  gap: "var(--space-4)",
                  padding: "var(--space-4) var(--space-2)",
                  borderBottom: "1px solid var(--color-surface-3)",
                  borderTop: i === 0 ? "1px solid var(--color-surface-3)" : undefined,
                }}
              >
                {/* Name + status */}
                <div style={{ display: "flex", alignItems: "center", gap: "var(--space-3)" }}>
                  <p
                    style={{
                      fontSize: "var(--text-sm)",
                      fontWeight: "var(--weight-medium)",
                      color: "var(--color-ink)",
                      margin: 0,
                      whiteSpace: "nowrap",
                    }}
                  >
                    {p.name}
                  </p>
                  <Badge variant={p.enabled ? "done" : "default"}>
                    {p.enabled ? "启用" : "停用"}
                  </Badge>
                </div>

                {/* Base URL */}
                <span
                  className="mono"
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {p.base_url}
                </span>

                {/* Models */}
                <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)", justifyContent: "flex-end" }}>
                  {p.models.map((m) => (
                    <Badge key={m} variant="outline">{m}</Badge>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        <ProviderForm onSuccess={() => qc.invalidateQueries({ queryKey: ["providers"] })} />
      </section>

      {/* Role bindings */}
      <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <h2
            style={{
              fontSize: "var(--text-lg)",
              fontWeight: "var(--weight-semi)",
              color: "var(--color-ink)",
              letterSpacing: "-0.02em",
              margin: "0 0 var(--space-1) 0",
            }}
          >
            角色绑定
          </h2>
          <p style={{ fontSize: "var(--text-sm)", color: "var(--color-ink-3)", margin: 0 }}>
            将不同 AI 任务角色绑定到特定 Provider 和模型
          </p>
        </div>

        <div style={{ display: "flex", flexDirection: "column" }}>
          {(["writer", "reviewer", "lite"] as Role[]).map((role) => {
            const current = bindings.data?.find((b) => b.role === role);
            return (
              <RoleRow
                key={role}
                role={role}
                providers={providers.data ?? []}
                current={current}
                onSave={(b) => upsertBinding.mutate(b)}
                isSaving={savingRole === role && upsertBinding.isPending}
              />
            );
          })}
        </div>
      </section>

      {/* Usage dashboard — kept as-is */}
      <UsageDashboard />
    </div>
  );
}
