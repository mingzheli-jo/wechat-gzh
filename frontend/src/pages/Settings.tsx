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
    </div>
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
