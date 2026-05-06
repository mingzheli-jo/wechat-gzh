import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Badge,
  Button,
  EmptyState,
  EyebrowLabel,
  PageSpinner,
} from "../components/ui";

type LibraryStatus = "pending" | "processing" | "done" | "failed";

type LibraryItem = {
  id: string;
  source_url: string;
  original_title: string | null;
  status: LibraryStatus;
  tags: string[] | null;
  error_msg: string | null;
};

type AccountMin = { id: string; name: string };

const STATUS_BADGE: Record<LibraryStatus, "pending" | "processing" | "done" | "failed"> = {
  pending: "pending",
  processing: "processing",
  done: "done",
  failed: "failed",
};

const STATUS_LABEL: Record<LibraryStatus, string> = {
  pending: "待抓取",
  processing: "抓取中",
  done: "完成",
  failed: "失败",
};

const STATUS_BAR_ORDER: LibraryStatus[] = ["pending", "processing", "done", "failed"];

const EMPTY_STATUS_COUNTS: Record<LibraryStatus, number> = {
  pending: 0,
  processing: 0,
  done: 0,
  failed: 0,
};

export default function Library() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [accountId, setAccountId] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: async () => (await api.get<LibraryItem[]>("/library")).data,
    refetchInterval: 5000,
  });

  const accounts = useQuery({
    queryKey: ["accounts-min"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const ingest = useMutation({
    mutationFn: async () => {
      const urls = text.split("\n").map((u) => u.trim()).filter(Boolean);
      return api.post("/library", {
        urls,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
    },
    onSuccess: () => {
      setText("");
      setTags("");
      qc.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const retry = useMutation({
    mutationFn: async (id: string) => api.post(`/library/${id}/retry`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });

  const triggerRewrite = useMutation({
    mutationFn: async () =>
      api.post("/drafts/rewrite", {
        library_item_ids: Array.from(selected),
        account_id: accountId,
      }),
    onSuccess: () => {
      setSelected(new Set());
      navigate("/drafts");
    },
  });

  function toggle(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  const urlCount = text.split("\n").filter((l) => l.trim()).length;

  const statusCounts = useMemo(() => {
    if (!data) return EMPTY_STATUS_COUNTS;
    const counts: Record<LibraryStatus, number> = {
      pending: 0,
      processing: 0,
      done: 0,
      failed: 0,
    };
    for (const item of data) {
      counts[item.status]++;
    }
    return counts;
  }, [data]);

  return (
    <div className="page-shell" style={{ paddingBottom: "var(--space-24)" }}>
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">素材库</h1>
          <p className="text-page-subtitle">粘贴微信公众号文章链接，抓取后选择目标公众号批量改写</p>
        </div>

        {/* Status mini-stats row */}
        {data && data.length > 0 && (
          <div style={{ display: "flex", gap: "var(--space-6)", flexShrink: 0, alignItems: "flex-end" }}>
            {STATUS_BAR_ORDER.map((status) => {
              const count = statusCounts[status];
              const isProcessing = status === "processing" && count > 0;
              const isFailedAlert = status === "failed" && count > 0;
              return (
                <div key={status} style={{ textAlign: "right" }}>
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <span
                      className="text-stat"
                      style={{
                        color: isFailedAlert ? "var(--color-failed-fg)" : "var(--color-ink)",
                        transition: "color var(--dur-normal)",
                      }}
                    >
                      {count}
                    </span>
                    {isProcessing && (
                      <span
                        aria-hidden="true"
                        style={{
                          position: "absolute",
                          top: 0,
                          right: "-8px",
                          width: "5px",
                          height: "5px",
                          borderRadius: "50%",
                          backgroundColor: "var(--color-processing-fg)",
                          animation: "pulse 1.2s ease-in-out infinite",
                        }}
                      />
                    )}
                  </div>
                  <EyebrowLabel
                    style={{
                      display: "block",
                      marginTop: "var(--space-1)",
                      color: isFailedAlert ? "var(--color-failed-fg)" : undefined,
                    }}
                  >
                    {STATUS_LABEL[status]}
                  </EyebrowLabel>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Two-pane layout: list (left) | add panel (right) */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: "var(--space-8)",
          alignItems: "start",
        }}
      >
        {/* LEFT — article list */}
        <div>
          {isLoading ? (
            <PageSpinner />
          ) : !data || data.length === 0 ? (
            <EmptyState
              icon={
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
                  <rect x="8" y="10" width="24" height="22" rx="3" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M14 17h12M14 22h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              }
              title="素材库为空"
              description="在右侧粘贴文章链接开始抓取"
            />
          ) : (
            <div className="ed-table">
              {data.map((item, i) => {
                const isSelected = selected.has(item.id);
                const indexStr = String(i + 1).padStart(2, "0");
                return (
                  <div
                    key={item.id}
                    className="ed-row"
                    style={{
                      gridTemplateColumns: "32px 1fr auto",
                      cursor: item.status === "done" ? "pointer" : "default",
                      animation: `fade-in var(--dur-normal) ${i * 30}ms var(--ease-out) both`,
                      // Selected state: subtle bg + left accent
                      backgroundColor: isSelected ? "var(--color-surface-2)" : undefined,
                      borderLeft: isSelected ? "2px solid var(--color-ink)" : "2px solid transparent",
                      paddingLeft: "calc(var(--space-2) - 2px)",
                    }}
                    onClick={() => item.status === "done" && toggle(item.id)}
                  >
                    {/* Index */}
                    <span
                      className="ed-row-index"
                      style={{
                        color: isSelected ? "var(--color-ink)" : undefined,
                      }}
                    >
                      {indexStr}
                    </span>

                    {/* Content */}
                    <div style={{ minWidth: 0 }}>
                      <p className="ed-row-title" style={{ margin: 0 }}>
                        {item.original_title ?? "（待抓取）"}
                      </p>
                      <p
                        className="mono"
                        style={{
                          margin: "var(--space-1) 0 0 0",
                          overflow: "hidden",
                          textOverflow: "ellipsis",
                          whiteSpace: "nowrap",
                        }}
                      >
                        {item.source_url}
                      </p>
                      {item.tags && item.tags.length > 0 && (
                        <div
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: "var(--space-1)",
                            marginTop: "var(--space-2)",
                          }}
                        >
                          {item.tags.map((t) => (
                            <Badge key={t} variant="outline">{t}</Badge>
                          ))}
                        </div>
                      )}
                      {item.error_msg && (
                        <p
                          style={{
                            fontSize: "var(--text-xs)",
                            color: "var(--color-failed-fg)",
                            margin: "var(--space-1) 0 0 0",
                          }}
                        >
                          {item.error_msg}
                        </p>
                      )}
                    </div>

                    {/* Status + retry */}
                    <div
                      style={{
                        display: "flex",
                        flexDirection: "column",
                        alignItems: "flex-end",
                        gap: "var(--space-2)",
                        flexShrink: 0,
                      }}
                    >
                      <Badge variant={STATUS_BADGE[item.status]}>
                        {item.status === "processing" && (
                          <span
                            style={{
                              display: "inline-block",
                              width: "6px",
                              height: "6px",
                              borderRadius: "50%",
                              backgroundColor: "currentColor",
                              animation: "pulse 1.2s ease-in-out infinite",
                              marginRight: "4px",
                            }}
                          />
                        )}
                        {STATUS_LABEL[item.status]}
                      </Badge>
                      {item.status === "failed" && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            retry.mutate(item.id);
                          }}
                          style={{
                            fontSize: "var(--text-xs)",
                            color: "var(--color-link)",
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            textDecoration: "underline",
                          }}
                        >
                          重试
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* RIGHT — add article panel (sticky) */}
        <div
          className="surface-panel"
          style={{
            padding: "var(--space-5)",
            position: "sticky",
            top: "var(--space-8)",
          }}
        >
          <EyebrowLabel
            as="h2"
            style={{ color: "var(--color-ink)", margin: "0 0 var(--space-4) 0" }}
          >
            添加文章
          </EyebrowLabel>

          <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
            <div>
              <label htmlFor="urls" className="field-label">
                文章 URL
                <span className="field-hint">一行一个</span>
              </label>
              <textarea
                id="urls"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={"https://mp.weixin.qq.com/s/...\nhttps://mp.weixin.qq.com/s/..."}
                rows={6}
                className="input-base input-mono"
                style={{ resize: "vertical", lineHeight: "var(--leading-normal)" }}
              />
            </div>

            <div>
              <label htmlFor="tags" className="field-label">
                标签
                <span className="field-hint">逗号分隔，选填</span>
              </label>
              <input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="职场, 母婴, 健康"
                className="input-base"
              />
            </div>

            <Button
              onClick={() => ingest.mutate()}
              disabled={!text.trim()}
              loading={ingest.isPending}
              style={{ width: "100%", marginTop: "var(--space-1)" }}
            >
              {ingest.isPending ? "提交中…" : `添加抓取${urlCount > 0 ? `（${urlCount} 条）` : ""}`}
            </Button>

            {ingest.isError && (
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", margin: 0 }}>
                提交失败，请重试
              </p>
            )}
          </div>
        </div>
      </div>

      {/* Bottom action bar */}
      {selected.size > 0 && (
        <div className="action-bar">
          <span style={{ fontSize: "var(--text-sm)", whiteSpace: "nowrap", flexShrink: 0 }}>
            已选 <strong>{selected.size}</strong> 篇
          </span>

          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            style={{
              flex: 1,
              minWidth: "160px",
              padding: "var(--space-2) var(--space-3)",
              fontSize: "var(--text-sm)",
              color: accountId ? "var(--color-white)" : "rgba(255,255,255,0.45)",
              backgroundColor: "rgba(255,255,255,0.1)",
              border: "1px solid rgba(255,255,255,0.2)",
              borderRadius: "var(--radius-md)",
              outline: "none",
              cursor: "pointer",
            }}
          >
            <option value="" style={{ color: "var(--color-ink)", backgroundColor: "var(--color-white)" }}>
              选择目标公众号
            </option>
            {accounts.data?.map((a) => (
              <option
                key={a.id}
                value={a.id}
                style={{ color: "var(--color-ink)", backgroundColor: "var(--color-white)" }}
              >
                {a.name}
              </option>
            ))}
          </select>

          <Button
            variant="secondary"
            size="sm"
            onClick={() => triggerRewrite.mutate()}
            disabled={!accountId}
            loading={triggerRewrite.isPending}
            style={{
              backgroundColor: "var(--color-white)",
              color: "var(--color-ink)",
              border: "none",
              flexShrink: 0,
            }}
          >
            {triggerRewrite.isPending ? "派发中…" : "开始改写"}
          </Button>

          <button
            onClick={() => setSelected(new Set())}
            style={{
              background: "none",
              border: "none",
              color: "rgba(255,255,255,0.5)",
              cursor: "pointer",
              padding: "var(--space-1)",
              flexShrink: 0,
              display: "flex",
              alignItems: "center",
            }}
            aria-label="清空选择"
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M11 3L3 11M3 3l8 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
