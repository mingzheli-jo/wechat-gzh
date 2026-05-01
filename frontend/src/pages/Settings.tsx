import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { api } from "../api/client";

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

type FormState = {
  name: string;
  base_url: string;
  api_key: string;
  models: string;
};

const FORM_KEYS: (keyof FormState)[] = ["name", "base_url", "api_key", "models"];

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

  const [form, setForm] = useState<FormState>({
    name: "",
    base_url: "",
    api_key: "",
    models: "",
  });

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
      setForm({ name: "", base_url: "", api_key: "", models: "" });
      qc.invalidateQueries({ queryKey: ["providers"] });
    },
  });

  const upsertBinding = useMutation({
    mutationFn: async (b: Binding) =>
      api.put("/ai-providers/role-bindings", b),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["bindings"] }),
  });

  return (
    <div className="p-8 space-y-8 max-w-3xl">
      <section>
        <h2 className="text-xl font-semibold mb-3">AI 服务商</h2>
        <ul className="space-y-2 mb-4">
          {providers.data?.map((p) => (
            <li key={p.id} className="border rounded p-3">
              <div className="font-medium">{p.name}</div>
              <div className="text-xs text-slate-500">{p.base_url}</div>
              <div className="text-xs">
                模型: {p.models.join(", ") || "(未配置)"}
              </div>
            </li>
          ))}
        </ul>
        <div className="border rounded p-4 space-y-2">
          <h3 className="font-medium">添加 Provider</h3>
          {FORM_KEYS.map((k) => (
            <input
              key={k}
              className="w-full border rounded px-3 py-2"
              placeholder={k === "models" ? "模型列表（逗号分隔）" : k}
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
            />
          ))}
          <button
            onClick={() => create.mutate()}
            className="bg-slate-900 text-white px-4 py-2 rounded"
          >
            添加
          </button>
        </div>
      </section>

      <section>
        <h2 className="text-xl font-semibold mb-3">角色绑定</h2>
        {(["writer", "reviewer", "lite"] as Role[]).map((role) => {
          const current = bindings.data?.find((b) => b.role === role);
          return (
            <RoleRow
              key={role}
              role={role}
              providers={providers.data ?? []}
              current={current}
              onSave={(b) => upsertBinding.mutate(b)}
            />
          );
        })}
      </section>

      <UsageDashboard />
    </div>
  );
}

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
  const maxDay =
    u.daily.reduce((m, d) => Math.max(m, d.cost_estimate), 0) || 1;

  return (
    <section>
      <h2 className="text-xl font-semibold mb-3">AI 用量（近 30 天）</h2>
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="border rounded p-3">
          <div className="text-xs text-slate-500">总成本（估算）</div>
          <div className="text-2xl font-semibold">
            ${u.total_cost.toFixed(4)}
          </div>
        </div>
        <div className="border rounded p-3">
          <div className="text-xs text-slate-500">Prompt tokens</div>
          <div className="text-2xl font-semibold">
            {u.total_prompt_tokens.toLocaleString()}
          </div>
        </div>
        <div className="border rounded p-3">
          <div className="text-xs text-slate-500">Completion tokens</div>
          <div className="text-2xl font-semibold">
            {u.total_completion_tokens.toLocaleString()}
          </div>
        </div>
      </div>

      {u.daily.length > 0 && (
        <div className="border rounded p-3 mb-4">
          <div className="text-xs text-slate-500 mb-2">每日成本</div>
          <div className="flex items-end gap-1 h-20">
            {u.daily.map((d) => (
              <div
                key={d.day}
                className="flex-1 bg-slate-700 rounded-t"
                style={{ height: `${(d.cost_estimate / maxDay) * 100}%` }}
                title={`${d.day}: $${d.cost_estimate.toFixed(4)}`}
              />
            ))}
          </div>
          <div className="flex justify-between text-xs text-slate-500 mt-1">
            <span>{u.daily[0]?.day}</span>
            <span>{u.daily[u.daily.length - 1]?.day}</span>
          </div>
        </div>
      )}

      {u.by_role.length > 0 && (
        <table className="w-full text-sm border">
          <thead className="bg-slate-100">
            <tr>
              <th className="p-2 text-left">角色</th>
              <th className="p-2 text-left">Provider/Model</th>
              <th className="p-2 text-right">次数</th>
              <th className="p-2 text-right">Tokens</th>
              <th className="p-2 text-right">成本</th>
            </tr>
          </thead>
          <tbody>
            {u.by_role.map((r, i) => (
              <tr key={i} className="border-t">
                <td className="p-2">{r.role ?? "-"}</td>
                <td className="p-2">
                  {r.provider ?? "-"} / {r.model}
                </td>
                <td className="p-2 text-right">{r.calls}</td>
                <td className="p-2 text-right">
                  {(r.prompt_tokens + r.completion_tokens).toLocaleString()}
                </td>
                <td className="p-2 text-right">
                  ${r.cost_estimate.toFixed(4)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}

type RoleRowProps = {
  role: Role;
  providers: Provider[];
  current: Binding | undefined;
  onSave: (b: Binding) => void;
};

function RoleRow({ role, providers, current, onSave }: RoleRowProps) {
  const [providerId, setProviderId] = useState(current?.provider_id ?? "");
  const [model, setModel] = useState(current?.model ?? "");
  return (
    <div className="border rounded p-3 mb-2 flex gap-2 items-center">
      <span className="w-20 font-medium">{role}</span>
      <select
        className="border rounded px-2 py-1"
        value={providerId}
        onChange={(e) => setProviderId(e.target.value)}
      >
        <option value="">— 选 Provider —</option>
        {providers.map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </select>
      <input
        className="border rounded px-2 py-1"
        placeholder="模型 ID"
        value={model}
        onChange={(e) => setModel(e.target.value)}
      />
      <button
        className="ml-auto bg-slate-900 text-white px-3 py-1 rounded text-sm"
        onClick={() => onSave({ role, provider_id: providerId, model })}
        disabled={!providerId || !model}
      >
        保存
      </button>
    </div>
  );
}
