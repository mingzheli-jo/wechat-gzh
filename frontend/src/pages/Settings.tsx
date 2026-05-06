import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { Badge, Button, Card, EyebrowLabel, Input, PageSpinner } from "../components/ui";

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
      style={{
        border: "1px solid var(--color-surface-3)",
        borderRadius: "var(--radius-lg)",
        padding: "var(--space-5)",
        backgroundColor: "var(--color-surface-2)",
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
        <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)" }}>
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

  return (
    <div
      style={{
        display: "grid",
        gridTemplateColumns: "140px 1fr 1fr auto",
        gap: "var(--space-3)",
        alignItems: "end",
        padding: "var(--space-4)",
        backgroundColor: "var(--color-surface-2)",
        borderRadius: "var(--radius-md)",
        border: "1px solid var(--color-surface-3)",
      }}
    >
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

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label style={{ fontSize: "var(--text-xs)", fontWeight: "var(--weight-medium)", color: "var(--color-ink-2)" }}>
          Provider
        </label>
        <select
          value={providerId}
          onChange={(e) => {
            setProviderId(e.target.value);
            setModel("");
          }}
          style={{
            padding: "var(--space-2) var(--space-3)",
            fontSize: "var(--text-sm)",
            color: "var(--color-ink)",
            backgroundColor: "var(--color-white)",
            border: "1px solid var(--color-surface-3)",
            borderRadius: "var(--radius-md)",
            outline: "none",
            cursor: "pointer",
          }}
        >
          <option value="">— 选择 —</option>
          {providers.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-1)" }}>
        <label style={{ fontSize: "var(--text-xs)", fontWeight: "var(--weight-medium)", color: "var(--color-ink-2)" }}>
          模型
        </label>
        {selectedProvider && selectedProvider.models.length > 0 ? (
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            style={{
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--text-sm)",
              fontFamily: "var(--font-mono)",
              color: "var(--color-ink)",
              backgroundColor: "var(--color-white)",
              border: "1px solid var(--color-surface-3)",
              borderRadius: "var(--radius-md)",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="">— 选择模型 —</option>
            {selectedProvider.models.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={model}
            onChange={(e) => setModel(e.target.value)}
            placeholder="模型 ID"
            style={{
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--text-sm)",
              fontFamily: "var(--font-mono)",
              color: "var(--color-ink)",
              backgroundColor: "var(--color-white)",
              border: "1px solid var(--color-surface-3)",
              borderRadius: "var(--radius-md)",
              outline: "none",
            }}
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

function UsageDashboard() {
  const usage = useQuery({
    queryKey: ["usage-summary"],
    queryFn: async () =>
      (await api.get<UsageSummary>("/usage/summary?days=30")).data,
  });

  if (!usage.data) return null;
  const u = usage.data;
  const maxDay = u.daily.reduce((m, d) => Math.max(m, d.cost_estimate), 0) || 1;

  return (
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
        AI 用量
      </h2>

      {/* Summary cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "var(--space-3)" }}>
        {[
          { label: "总成本（估算）", value: `$${u.total_cost.toFixed(4)}` },
          { label: "Prompt tokens", value: u.total_prompt_tokens.toLocaleString() },
          { label: "Completion tokens", value: u.total_completion_tokens.toLocaleString() },
        ].map(({ label, value }) => (
          <div
            key={label}
            style={{
              padding: "var(--space-4) var(--space-5)",
              backgroundColor: "var(--color-white)",
              border: "1px solid var(--color-surface-3)",
              borderRadius: "var(--radius-lg)",
            }}
          >
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)", margin: "0 0 var(--space-1) 0" }}>
              {label}
            </p>
            <p
              style={{
                fontSize: "var(--text-2xl)",
                fontWeight: "var(--weight-semi)",
                color: "var(--color-ink)",
                letterSpacing: "-0.02em",
                margin: 0,
                fontVariantNumeric: "tabular-nums",
              }}
            >
              {value}
            </p>
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-4)", margin: "var(--space-1) 0 0 0" }}>
              近 30 天
            </p>
          </div>
        ))}
      </div>

      {/* Bar chart */}
      {u.daily.length > 0 && (
        <div
          style={{
            padding: "var(--space-5)",
            backgroundColor: "var(--color-white)",
            border: "1px solid var(--color-surface-3)",
            borderRadius: "var(--radius-lg)",
          }}
        >
          <EyebrowLabel style={{ margin: "0 0 var(--space-4) 0" }}>
            每日成本
          </EyebrowLabel>
          <div style={{ display: "flex", alignItems: "flex-end", gap: "3px", height: "64px" }}>
            {u.daily.map((d) => (
              <div
                key={d.day}
                title={`${d.day}: $${d.cost_estimate.toFixed(4)}`}
                style={{
                  flex: 1,
                  height: `${Math.max(2, (d.cost_estimate / maxDay) * 100)}%`,
                  backgroundColor: "var(--color-ink)",
                  borderRadius: "2px 2px 0 0",
                  opacity: d.cost_estimate > 0 ? 1 : 0.15,
                  transition: "opacity var(--dur-fast)",
                  cursor: "default",
                }}
              />
            ))}
          </div>
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              marginTop: "var(--space-2)",
            }}
          >
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-4)" }}>{u.daily[0]?.day}</span>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-4)" }}>
              {u.daily[u.daily.length - 1]?.day}
            </span>
          </div>
        </div>
      )}

      {/* By-role table */}
      {u.by_role.length > 0 && (
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
              {u.by_role.map((r, i) => (
                <tr
                  key={i}
                  style={{ borderTop: i > 0 ? "1px solid var(--color-surface-2)" : "none" }}
                >
                  <td style={{ padding: "var(--space-3) var(--space-4)" }}>
                    <Badge variant="default">{r.role ?? "—"}</Badge>
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", color: "var(--color-ink-2)" }}>
                    {r.provider ?? "—"} / {r.model}
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {r.calls}
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                    {(r.prompt_tokens + r.completion_tokens).toLocaleString()}
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontVariantNumeric: "tabular-nums", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)" }}>
                    ${r.cost_estimate.toFixed(4)}
                  </td>
                </tr>
              ))}
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
    <div
      style={{
        maxWidth: "var(--max-narrow)",
        margin: "0 auto",
        padding: "var(--space-8)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-10)",
      }}
    >
      {/* Page header */}
      <div>
        <h1
          style={{
            fontSize: "var(--text-xl)",
            fontWeight: "var(--weight-semi)",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          设置
        </h1>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-ink-3)", marginTop: "var(--space-1)" }}>
          AI 服务商配置与角色绑定
        </p>
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
          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
            {providers.data.map((p) => (
              <Card key={p.id} padding="md">
                <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-4)" }}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-1)" }}>
                      <p
                        style={{
                          fontSize: "var(--text-base)",
                          fontWeight: "var(--weight-medium)",
                          color: "var(--color-ink)",
                          margin: 0,
                        }}
                      >
                        {p.name}
                      </p>
                      <Badge variant={p.enabled ? "done" : "default"}>
                        {p.enabled ? "启用" : "停用"}
                      </Badge>
                    </div>
                    <p
                      style={{
                        fontSize: "var(--text-xs)",
                        fontFamily: "var(--font-mono)",
                        color: "var(--color-ink-3)",
                        margin: "0 0 var(--space-2) 0",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {p.base_url}
                    </p>
                    {p.models.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)" }}>
                        {p.models.map((m) => (
                          <Badge key={m} variant="outline">
                            {m}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}

        <ProviderForm onSuccess={() => qc.invalidateQueries({ queryKey: ["providers"] })} />
      </section>

      {/* Role bindings */}
      <section style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
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

        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
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

      {/* Usage dashboard */}
      <UsageDashboard />
    </div>
  );
}
