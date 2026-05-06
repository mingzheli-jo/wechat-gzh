import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Badge,
  Button,
  EmptyState,
  EyebrowLabel,
  HairlineRule,
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

// Display order for the top status bar.
const STATUS_BAR_ORDER: LibraryStatus[] = [
  "pending",
  "processing",
  "done",
  "failed",
];

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
    <div
      style={{
        maxWidth: "var(--max-content)",
        margin: "0 auto",
        padding: "var(--space-8) var(--space-8) var(--space-20)",
      }}
    >
      {/* Page header */}
      <div style={{ marginBottom: "var(--space-5)" }}>
        <h1
          style={{
            fontSize: "var(--text-xl)",
            fontWeight: "var(--weight-semi)",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          素材库
        </h1>
        <p style={{ fontSize: "var(--text-sm)", color: "var(--color-ink-3)", marginTop: "var(--space-1)" }}>
          粘贴微信公众号文章链接，抓取后选择目标公众号批量改写
        </p>
      </div>

      {/* Status bar */}
      {data && data.length > 0 && (
        <>
          <div
            style={{
              display: "flex",
              gap: "var(--space-6)",
              marginBottom: "var(--space-3)",
            }}
          >
            {STATUS_BAR_ORDER.map((status) => {
              const count = statusCounts[status];
              const isProcessing = status === "processing" && count > 0;
              const isFailedAlert = status === "failed" && count > 0;
              return (
                <div key={status} style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ position: "relative", display: "inline-block" }}>
                    <span
                      style={{
                        fontSize: "var(--text-2xl)",
                        fontWeight: "var(--weight-semi)",
                        fontFamily: "var(--font-mono)",
                        fontVariantNumeric: "tabular-nums",
                        letterSpacing: "-0.02em",
                        lineHeight: 1,
                        color: isFailedAlert
                          ? "var(--color-failed-fg)"
                          : "var(--color-ink)",
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
                      marginTop: "var(--space-1)",
                      color: isFailedAlert
                        ? "var(--color-failed-fg)"
                        : "var(--color-ink-3)",
                    }}
                  >
                    {STATUS_LABEL[status]}
                  </EyebrowLabel>
                </div>
              );
            })}
          </div>
          <HairlineRule style={{ marginBottom: "var(--space-6)" }} />
        </>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 2fr", gap: "var(--space-6)", alignItems: "start" }}>
        {/* Input panel */}
        <div
          style={{
            backgroundColor: "var(--color-white)",
            border: "1px solid var(--color-surface-3)",
            borderRadius: "var(--radius-lg)",
            padding: "var(--space-5)",
            position: "sticky",
            top: "calc(var(--nav-height) + var(--space-6))",
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
              <label
                htmlFor="urls"
                style={{
                  display: "block",
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--weight-medium)",
                  color: "var(--color-ink-2)",
                  marginBottom: "var(--space-1)",
                }}
              >
                文章 URL
                <span style={{ color: "var(--color-ink-4)", fontWeight: "var(--weight-normal)", marginLeft: "var(--space-2)" }}>
                  一行一个
                </span>
              </label>
              <textarea
                id="urls"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={"https://mp.weixin.qq.com/s/...\nhttps://mp.weixin.qq.com/s/..."}
                rows={6}
                style={{
                  width: "100%",
                  padding: "var(--space-3)",
                  fontSize: "var(--text-xs)",
                  fontFamily: "var(--font-mono)",
                  color: "var(--color-ink)",
                  backgroundColor: "var(--color-surface-2)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  outline: "none",
                  resize: "vertical",
                  lineHeight: "var(--leading-normal)",
                  transition: "border-color var(--dur-fast)",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-ink)"; e.currentTarget.style.backgroundColor = "var(--color-white)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-surface-3)"; e.currentTarget.style.backgroundColor = "var(--color-surface-2)"; }}
              />
            </div>

            <div>
              <label
                htmlFor="tags"
                style={{
                  display: "block",
                  fontSize: "var(--text-sm)",
                  fontWeight: "var(--weight-medium)",
                  color: "var(--color-ink-2)",
                  marginBottom: "var(--space-1)",
                }}
              >
                标签
                <span style={{ color: "var(--color-ink-4)", fontWeight: "var(--weight-normal)", marginLeft: "var(--space-2)" }}>
                  逗号分隔，选填
                </span>
              </label>
              <input
                id="tags"
                value={tags}
                onChange={(e) => setTags(e.target.value)}
                placeholder="职场, 母婴, 健康"
                style={{
                  width: "100%",
                  padding: "var(--space-2) var(--space-3)",
                  fontSize: "var(--text-sm)",
                  color: "var(--color-ink)",
                  backgroundColor: "var(--color-surface-2)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  outline: "none",
                  transition: "border-color var(--dur-fast)",
                  boxSizing: "border-box",
                }}
                onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-ink)"; e.currentTarget.style.backgroundColor = "var(--color-white)"; }}
                onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-surface-3)"; e.currentTarget.style.backgroundColor = "var(--color-surface-2)"; }}
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
              <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)" }}>
                提交失败，请重试
              </p>
            )}
          </div>
        </div>

        {/* List panel */}
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
              description="在左侧粘贴文章链接开始抓取"
            />
          ) : (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                borderTop: "1px solid var(--color-surface-3)",
              }}
            >
              {data.map((item, i) => {
                const isSelected = selected.has(item.id);
                return (
                <div
                  key={item.id}
                  style={{
                    position: "relative",
                    backgroundColor: "transparent",
                    borderBottom: "1px solid var(--color-surface-3)",
                    padding: "var(--space-4) var(--space-5)",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: "var(--space-4)",
                    transition: "background-color var(--dur-fast)",
                    cursor: item.status === "done" ? "pointer" : "default",
                    animation: `fade-in var(--dur-normal) ${i * 30}ms var(--ease-out) both`,
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor =
                      "var(--color-surface-2)";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = "transparent";
                  }}
                  onClick={() => item.status === "done" && toggle(item.id)}
                >
                  {/* Selection indicator (left edge bar) */}
                  <span
                    aria-hidden="true"
                    style={{
                      position: "absolute",
                      top: 0,
                      bottom: 0,
                      left: 0,
                      width: "3px",
                      backgroundColor: "var(--color-ink)",
                      opacity: isSelected ? 1 : 0,
                      transition: "opacity var(--dur-fast)",
                    }}
                  />

                  {/* Checkbox */}
                  <div style={{ paddingTop: "2px", flexShrink: 0 }}>
                    <input
                      type="checkbox"
                      disabled={item.status !== "done"}
                      checked={isSelected}
                      onChange={() => toggle(item.id)}
                      onClick={(e) => e.stopPropagation()}
                      style={{
                        width: "16px",
                        height: "16px",
                        cursor: item.status === "done" ? "pointer" : "not-allowed",
                        accentColor: "var(--color-ink)",
                      }}
                      aria-label={`选择 ${item.original_title ?? item.source_url}`}
                    />
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        fontSize: "var(--text-sm)",
                        fontWeight: "var(--weight-medium)",
                        color: "var(--color-ink)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        marginBottom: "var(--space-1)",
                      }}
                    >
                      {item.original_title ?? "（待抓取）"}
                    </div>
                    <div
                      style={{
                        fontSize: "var(--text-xs)",
                        color: "var(--color-ink-3)",
                        fontFamily: "var(--font-mono)",
                        whiteSpace: "nowrap",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        marginBottom: item.tags?.length || item.error_msg ? "var(--space-2)" : 0,
                      }}
                    >
                      {item.source_url}
                    </div>

                    {item.tags && item.tags.length > 0 && (
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)", marginTop: "var(--space-1)" }}>
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
                          marginTop: "var(--space-1)",
                          margin: "var(--space-1) 0 0",
                        }}
                      >
                        {item.error_msg}
                      </p>
                    )}
                  </div>

                  {/* Status + action */}
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: "var(--space-2)", flexShrink: 0 }}>
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
                          }}
                        />
                      )}
                      {STATUS_LABEL[item.status]}
                    </Badge>
                    {item.status === "failed" && (
                      <button
                        onClick={(e) => { e.stopPropagation(); retry.mutate(item.id); }}
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
      </div>

      {/* Bottom action bar */}
      {selected.size > 0 && (
        <div
          style={{
            position: "fixed",
            bottom: "var(--space-6)",
            left: "50%",
            transform: "translateX(-50%)",
            backgroundColor: "var(--color-ink)",
            color: "var(--color-accent-fg)",
            borderRadius: "var(--radius-xl)",
            padding: "var(--space-3) var(--space-4)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-4)",
            boxShadow: "var(--shadow-xl)",
            animation: "slide-up var(--dur-slow) var(--ease-out) both",
            zIndex: 30,
            minWidth: "480px",
          }}
        >
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
              color: selected.size > 0 && !accountId ? "rgba(255,255,255,0.4)" : "var(--color-white)",
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
              fontSize: "var(--text-xs)",
              cursor: "pointer",
              padding: "var(--space-1)",
              flexShrink: 0,
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
