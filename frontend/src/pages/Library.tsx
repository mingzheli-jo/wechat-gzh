import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Badge,
  Button,
  ConfirmModal,
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
  rewrite_count: number;
};

type AccountMin = { id: string; name: string };

type GroupKey = "newAdded" | "active" | "ready" | "rewritten" | "failed";

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

const GROUP_ORDER: GroupKey[] = ["newAdded", "active", "ready", "rewritten", "failed"];

const GROUP_LABEL: Record<GroupKey, string> = {
  newAdded: "本次新增",
  active: "进行中",
  ready: "可改写",
  rewritten: "已改写",
  failed: "失败",
};

const NEW_HIGHLIGHT_MS = 60_000;

function classify(item: LibraryItem, newAddedSet: Set<string>): GroupKey {
  if (newAddedSet.has(item.id)) return "newAdded";
  if (item.status === "pending" || item.status === "processing") return "active";
  if (item.status === "failed") return "failed";
  return item.rewrite_count > 0 ? "rewritten" : "ready";
}

function ChevronDown({ open }: { open: boolean }) {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      aria-hidden="true"
      style={{
        transform: open ? "rotate(0deg)" : "rotate(-90deg)",
        transition: "transform var(--dur-fast) var(--ease-out)",
      }}
    >
      <path
        d="M2.5 4l2.5 2.5L7.5 4"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Library() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [accountId, setAccountId] = useState<string>("");
  const [newAdded, setNewAdded] = useState<Set<string>>(new Set());
  const [collapsed, setCollapsed] = useState<Set<GroupKey>>(new Set(["rewritten"]));
  const [deleteModalOpen, setDeleteModalOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const newAddedTimers = useRef<Map<string, number>>(new Map());
  const deleteErrorTimer = useRef<number | null>(null);

  function flashError(msg: string) {
    setDeleteError(msg);
    if (deleteErrorTimer.current !== null) {
      window.clearTimeout(deleteErrorTimer.current);
    }
    deleteErrorTimer.current = window.setTimeout(() => {
      setDeleteError(null);
      deleteErrorTimer.current = null;
    }, 6000);
  }

  // Cleanup timers on unmount
  useEffect(() => {
    const timers = newAddedTimers.current;
    return () => {
      timers.forEach((id) => window.clearTimeout(id));
      timers.clear();
      if (deleteErrorTimer.current !== null) {
        window.clearTimeout(deleteErrorTimer.current);
      }
    };
  }, []);

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
      const res = await api.post<LibraryItem[]>("/library", {
        urls,
        tags: tags.split(",").map((t) => t.trim()).filter(Boolean),
      });
      return res.data;
    },
    onSuccess: (items) => {
      setText("");
      setTags("");
      qc.invalidateQueries({ queryKey: ["library"] });
      const ids = items.map((i) => i.id);
      setNewAdded((prev) => {
        const next = new Set(prev);
        ids.forEach((id) => next.add(id));
        return next;
      });
      ids.forEach((id) => {
        const handle = window.setTimeout(() => {
          setNewAdded((prev) => {
            const next = new Set(prev);
            next.delete(id);
            return next;
          });
          newAddedTimers.current.delete(id);
        }, NEW_HIGHLIGHT_MS);
        newAddedTimers.current.set(id, handle);
      });
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

  const deleteSelected = useMutation({
    mutationFn: async (ids: string[]) => {
      const results = await Promise.allSettled(
        ids.map((id) =>
          api.delete(`/library/${id}?cascade_drafts=true`)
        )
      );
      const failures: { id: string; status?: number; detail?: string }[] = [];
      results.forEach((r, i) => {
        if (r.status === "rejected") {
          const err = r.reason as {
            response?: { status?: number; data?: { detail?: unknown } };
          };
          const detail = err.response?.data?.detail;
          failures.push({
            id: ids[i],
            status: err.response?.status,
            detail:
              typeof detail === "string"
                ? detail
                : typeof detail === "object" && detail !== null && "message" in detail
                ? String((detail as { message?: unknown }).message ?? "")
                : undefined,
          });
        }
      });
      return { failures, total: ids.length };
    },
    onSuccess: ({ failures, total }) => {
      qc.invalidateQueries({ queryKey: ["library"] });
      qc.invalidateQueries({ queryKey: ["drafts"] });
      setDeleteModalOpen(false);
      if (failures.length === 0) {
        setSelected(new Set());
        return;
      }
      // Keep failed ids selected so user can see / retry
      const failedIds = new Set(failures.map((f) => f.id));
      setSelected(failedIds);
      const sample = failures[0];
      const reason = sample.detail
        ? sample.detail
        : sample.status === 409
        ? "其中含改写中的草稿，请等改写完成后再删"
        : "请稍后重试";
      flashError(`${failures.length}/${total} 篇删除失败：${reason}`);
    },
    onError: () => {
      setDeleteModalOpen(false);
      flashError("删除请求失败，请稍后重试");
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

  function toggleGroup(key: GroupKey) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
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

  const grouped = useMemo(() => {
    const map: Record<GroupKey, LibraryItem[]> = {
      newAdded: [],
      active: [],
      ready: [],
      rewritten: [],
      failed: [],
    };
    if (!data) return map;
    for (const item of data) {
      map[classify(item, newAdded)].push(item);
    }
    return map;
  }, [data, newAdded]);

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

      {deleteError && (
        <div
          role="alert"
          style={{
            margin: "0 0 var(--space-4) 0",
            padding: "var(--space-3) var(--space-4)",
            backgroundColor: "var(--color-failed)",
            color: "var(--color-failed-fg)",
            borderRadius: "var(--radius-md)",
            fontSize: "var(--text-sm)",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: "var(--space-3)",
            animation: "fade-in var(--dur-fast) var(--ease-out) both",
          }}
        >
          <span>{deleteError}</span>
          <button
            type="button"
            onClick={() => setDeleteError(null)}
            aria-label="关闭"
            style={{
              background: "none",
              border: "none",
              padding: 0,
              fontSize: "var(--text-xs)",
              color: "var(--color-failed-fg)",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            关闭
          </button>
        </div>
      )}

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
              {GROUP_ORDER.map((groupKey) => {
                const items = grouped[groupKey];
                // Hide groups with no items (except "ready" which we always show as primary action area)
                if (items.length === 0 && groupKey !== "ready") return null;
                const isCollapsed = collapsed.has(groupKey);
                const isHighlight = groupKey === "newAdded";
                return (
                  <div key={groupKey} className="ed-table-group">
                    {/* Group header (clickable to toggle) */}
                    <button
                      type="button"
                      onClick={() => toggleGroup(groupKey)}
                      className="ed-table-group-header"
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "var(--space-2)",
                        width: "100%",
                        background: "none",
                        border: "none",
                        padding: "var(--space-3) 0",
                        cursor: "pointer",
                        textAlign: "left",
                      }}
                    >
                      <span style={{ color: "var(--color-ink-3)", display: "flex", alignItems: "center" }}>
                        <ChevronDown open={!isCollapsed} />
                      </span>
                      <h2
                        className="ed-table-group-title"
                        style={{
                          margin: 0,
                          color: isHighlight ? "var(--color-ink)" : undefined,
                        }}
                      >
                        {GROUP_LABEL[groupKey]}
                      </h2>
                      <span className="ed-table-group-count">{items.length}</span>
                      {isHighlight && items.length > 0 && (
                        <span
                          aria-hidden="true"
                          style={{
                            display: "inline-block",
                            width: "6px",
                            height: "6px",
                            borderRadius: "50%",
                            backgroundColor: "var(--color-processing-fg)",
                            animation: "pulse 1.2s ease-in-out infinite",
                            marginLeft: "var(--space-1)",
                          }}
                        />
                      )}
                    </button>

                    {/* Rows */}
                    {!isCollapsed && (
                      items.length === 0 ? (
                        <div
                          style={{
                            padding: "var(--space-6) var(--space-2)",
                            fontSize: "var(--text-sm)",
                            color: "var(--color-ink-4)",
                            textAlign: "center",
                          }}
                        >
                          暂无
                        </div>
                      ) : (
                        items.map((item, i) => {
                          const isSelected = selected.has(item.id);
                          // Allow selection on done (for rewrite or delete)
                          // and failed (for delete only). Pending/processing
                          // rows aren't selectable.
                          const isClickable =
                            item.status === "done" || item.status === "failed";
                          const isRewritten = groupKey === "rewritten";
                          return (
                            <div
                              key={item.id}
                              className="ed-row"
                              style={{
                                gridTemplateColumns: "32px 1fr auto",
                                cursor: isClickable ? "pointer" : "default",
                                animation: `fade-in var(--dur-normal) ${i * 30}ms var(--ease-out) both`,
                                backgroundColor: isSelected ? "var(--color-surface-2)" : undefined,
                                borderLeft: isSelected
                                  ? "2px solid var(--color-ink)"
                                  : isHighlight
                                  ? "2px solid var(--color-processing-fg)"
                                  : "2px solid transparent",
                                paddingLeft: "calc(var(--space-2) - 2px)",
                                opacity: isRewritten ? 0.55 : 1,
                                transition: "opacity var(--dur-normal), background-color var(--dur-fast)",
                              }}
                              onClick={() => isClickable && toggle(item.id)}
                            >
                              {/* Index */}
                              <span
                                className="ed-row-index"
                                style={{ color: isSelected ? "var(--color-ink)" : undefined }}
                              >
                                {String(i + 1).padStart(2, "0")}
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

                              {/* Status + rewrite count + retry */}
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  alignItems: "flex-end",
                                  gap: "var(--space-2)",
                                  flexShrink: 0,
                                }}
                              >
                                <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center" }}>
                                  {item.rewrite_count > 0 && (
                                    <Badge variant="outline">
                                      已改写 ×{item.rewrite_count}
                                    </Badge>
                                  )}
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
                                </div>
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
                        })
                      )
                    )}
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
      {selected.size > 0 && (() => {
        const selectedItems = (data ?? []).filter((i) => selected.has(i.id));
        const canRewrite =
          selectedItems.length > 0 &&
          selectedItems.every((i) => i.status === "done");
        return (
          <div className="action-bar">
            <span style={{ fontSize: "var(--text-sm)", whiteSpace: "nowrap", flexShrink: 0 }}>
              已选 <strong>{selected.size}</strong> 篇
            </span>

            {canRewrite && (
              <>
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
              </>
            )}

            {!canRewrite && (
              <span style={{ flex: 1 }} />
            )}

            <button
              type="button"
              onClick={() => setDeleteModalOpen(true)}
              disabled={deleteSelected.isPending}
              style={{
                background: "none",
                border: "none",
                padding: "var(--space-2) var(--space-3)",
                fontSize: "var(--text-sm)",
                color: "var(--color-failed-fg)",
                cursor: deleteSelected.isPending ? "not-allowed" : "pointer",
                fontWeight: "var(--weight-medium)",
                flexShrink: 0,
                textDecoration: "underline",
              }}
            >
              {deleteSelected.isPending ? "删除中…" : "删除选中"}
            </button>

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
        );
      })()}

      <ConfirmModal
        open={deleteModalOpen}
        onClose={() => setDeleteModalOpen(false)}
        onConfirm={() => deleteSelected.mutate(Array.from(selected))}
        loading={deleteSelected.isPending}
        title="删除选中素材"
        message={`确认删除选中的 ${selected.size} 篇？关联的草稿（如有）会一并删除。改写中的草稿无法删除。`}
        confirmLabel="确认删除"
      />

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.3; }
        }
      `}</style>
    </div>
  );
}
