import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { creationsApi, type CreationStatus } from "../api/creations";
import { Badge, Button, EmptyState, EyebrowLabel, PageSpinner } from "../components/ui";

type AccountMin = { id: string; name: string };

type InputMode = "link" | "manual";

const STATUS_LABEL: Record<CreationStatus, string> = {
  pending: "排队中",
  extracting: "提炼主题",
  retrieving: "检索素材",
  generating: "生成中",
  reviewing: "核查中",
  done: "完成",
  failed: "失败",
};

function statusVariant(s: CreationStatus): "done" | "failed" | "processing" {
  if (s === "done") return "done";
  if (s === "failed") return "failed";
  return "processing";
}

const RUNNING: CreationStatus[] = [
  "pending",
  "extracting",
  "retrieving",
  "generating",
  "reviewing",
];

export default function Creator() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [mode, setMode] = useState<InputMode>("link");
  const [url, setUrl] = useState("");
  const [theme, setTheme] = useState("");
  const [accountId, setAccountId] = useState("");

  const list = useQuery({
    queryKey: ["creations"],
    queryFn: () => creationsApi.list({ page: 1, page_size: 50 }),
    refetchInterval: (query) => {
      const items = query.state.data?.items ?? [];
      return items.some((c) => RUNNING.includes(c.status)) ? 4000 : false;
    },
  });

  const accounts = useQuery({
    queryKey: ["accounts-min"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const create = useMutation({
    mutationFn: () =>
      creationsApi.create({
        source_url: mode === "link" ? url.trim() : undefined,
        theme: mode === "manual" ? theme.trim() : undefined,
        account_id: accountId || undefined,
      }),
    onSuccess: (created) => {
      setUrl("");
      setTheme("");
      qc.invalidateQueries({ queryKey: ["creations"] });
      navigate(`/creations/${created.id}`);
    },
  });

  const canSubmit = mode === "link" ? Boolean(url.trim()) : Boolean(theme.trim());

  return (
    <div className="page-shell" style={{ paddingBottom: "var(--space-24)" }}>
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">主题创作</h1>
          <p className="text-page-subtitle">
            从链接或主题出发，AI 提炼主题、检索文章库中的真实素材，并基于素材发散成文（不杜撰）
          </p>
        </div>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 380px",
          gap: "var(--space-8)",
          alignItems: "start",
        }}
      >
        {/* LEFT — creations list */}
        <div>
          {list.isLoading ? (
            <PageSpinner />
          ) : !list.data || list.data.items.length === 0 ? (
            <EmptyState
              icon={
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <path d="M10 8h16l4 4v20H10V8z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
                  <path d="M14 18h12M14 23h9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              }
              title="还没有创作"
              description="在右侧输入链接或主题，开始第一篇基于库内素材的创作"
            />
          ) : (
            <div className="ed-table">
              {list.data.items.map((c, i) => (
                <div
                  key={c.id}
                  className="ed-row"
                  style={{
                    gridTemplateColumns: "32px 1fr auto",
                    cursor: "pointer",
                    animation: `fade-in var(--dur-normal) ${i * 30}ms var(--ease-out) both`,
                  }}
                  onClick={() => navigate(`/creations/${c.id}`)}
                >
                  <span className="ed-row-index">{String(i + 1).padStart(2, "0")}</span>
                  <div style={{ minWidth: 0 }}>
                    <p className="ed-row-title" style={{ margin: 0 }}>
                      {c.generated_title ?? c.source_title ?? c.extracted_theme ?? "（创作中）"}
                    </p>
                    <p
                      style={{
                        margin: "var(--space-1) 0 0 0",
                        fontSize: "var(--text-xs)",
                        color: "var(--color-ink-3)",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {c.extracted_theme ?? "主题待提炼…"}
                    </p>
                    {c.error_msg && (
                      <p
                        style={{
                          fontSize: "var(--text-xs)",
                          color: "var(--color-failed-fg)",
                          margin: "var(--space-1) 0 0 0",
                        }}
                      >
                        {c.error_msg}
                      </p>
                    )}
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexShrink: 0 }}>
                    <Badge variant="outline">{c.input_mode === "link" ? "链接" : "主题"}</Badge>
                    <Badge variant={statusVariant(c.status)}>{STATUS_LABEL[c.status]}</Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* RIGHT — create panel */}
        <div
          className="surface-panel"
          style={{ padding: "var(--space-5)", position: "sticky", top: "var(--space-8)" }}
        >
          <EyebrowLabel as="h2" style={{ color: "var(--color-ink)", margin: "0 0 var(--space-4) 0" }}>
            新建创作
          </EyebrowLabel>

          {/* Mode toggle */}
          <div style={{ display: "flex", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
            {(["link", "manual"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                style={{
                  flex: 1,
                  padding: "var(--space-2)",
                  fontSize: "var(--text-sm)",
                  borderRadius: "var(--radius-sm)",
                  border: "1px solid var(--color-surface-3)",
                  background: mode === m ? "var(--color-ink)" : "none",
                  color: mode === m ? "var(--color-white)" : "var(--color-ink-3)",
                  cursor: "pointer",
                  transition: "all var(--dur-fast)",
                }}
              >
                {m === "link" ? "输入链接" : "手动主题"}
              </button>
            ))}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            {mode === "link" ? (
              <div>
                <label htmlFor="url" className="field-label">
                  文章链接
                  <span className="field-hint">微信公众号文章</span>
                </label>
                <input
                  id="url"
                  value={url}
                  onChange={(e) => setUrl(e.target.value)}
                  placeholder="https://mp.weixin.qq.com/s/..."
                  className="input-base input-mono"
                />
              </div>
            ) : (
              <div>
                <label htmlFor="theme" className="field-label">
                  主题
                  <span className="field-hint">约 100 字</span>
                </label>
                <textarea
                  id="theme"
                  value={theme}
                  onChange={(e) => setTheme(e.target.value)}
                  placeholder="直接描述你想写的主题…"
                  rows={5}
                  className="input-base"
                  style={{ resize: "vertical", lineHeight: "var(--leading-normal)" }}
                />
              </div>
            )}

            <div>
              <label htmlFor="account" className="field-label">
                目标公众号
                <span className="field-hint">选填，用于套用风格</span>
              </label>
              <select
                id="account"
                value={accountId}
                onChange={(e) => setAccountId(e.target.value)}
                className="input-base"
              >
                <option value="">不指定</option>
                {accounts.data?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.name}
                  </option>
                ))}
              </select>
            </div>

            <Button
              onClick={() => create.mutate()}
              disabled={!canSubmit}
              loading={create.isPending}
              style={{ width: "100%", marginTop: "var(--space-1)" }}
            >
              {create.isPending ? "提交中…" : "开始创作"}
            </Button>

            {create.isError && (
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", margin: 0 }}>
                提交失败，请重试
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
