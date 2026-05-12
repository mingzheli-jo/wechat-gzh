import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { Badge, EmptyState, EyebrowLabel, PageSpinner } from "../components/ui";

type Draft = {
  id: string;
  title: string | null;
  status: string;
  error_msg: string | null;
  review_report_id: string | null;
  created_at: string;
  source_url: string | null;
};

type DraftPage = {
  items: Draft[];
  total: number;
};

type GroupKey = "active" | "done" | "published" | "failed";

const PAGE_SIZE = 10;

const GROUPS: { key: GroupKey; label: string; canDelete: boolean }[] = [
  { key: "active", label: "进行中", canDelete: false },
  { key: "done", label: "待推送", canDelete: true },
  { key: "published", label: "已推送", canDelete: true },
  { key: "failed", label: "失败", canDelete: true },
];

const STATUS_BADGE: Record<string, "pending" | "processing" | "done" | "failed" | "warn"> = {
  draft: "processing",
  reviewing: "processing",
  reviewed: "done",
  failed: "failed",
  published_to_wechat: "done",
};

const STATUS_LABEL: Record<string, string> = {
  draft: "改写中",
  reviewing: "审核中",
  reviewed: "待推送",
  failed: "失败",
  published_to_wechat: "已推送",
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ChevronRight() {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      aria-hidden="true"
      style={{ display: "block" }}
    >
      <path
        d="M4.5 2.5L8 6l-3.5 3.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface PagerProps {
  page: number;
  total: number;
  onChange: (p: number) => void;
}

function Pager({ page, total, onChange }: PagerProps) {
  const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
  if (lastPage <= 1) return null;
  const baseBtn: React.CSSProperties = {
    background: "none",
    border: "none",
    padding: "var(--space-1) var(--space-2)",
    fontSize: "var(--text-xs)",
    fontFamily: "var(--font-mono)",
    color: "var(--color-ink-3)",
    cursor: "pointer",
  };
  const disabledBtn: React.CSSProperties = {
    color: "var(--color-ink-4)",
    cursor: "not-allowed",
  };
  return (
    <div
      style={{
        display: "flex",
        gap: "var(--space-2)",
        alignItems: "center",
        justifyContent: "flex-end",
        padding: "var(--space-3) var(--space-2)",
      }}
    >
      <button
        type="button"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        style={page <= 1 ? { ...baseBtn, ...disabledBtn } : baseBtn}
      >
        ‹ 上一页
      </button>
      <span
        className="mono"
        style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}
      >
        {page} / {lastPage}
      </span>
      <button
        type="button"
        onClick={() => onChange(page + 1)}
        disabled={page >= lastPage}
        style={page >= lastPage ? { ...baseBtn, ...disabledBtn } : baseBtn}
      >
        下一页 ›
      </button>
    </div>
  );
}

export default function Drafts() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [pages, setPages] = useState<Record<GroupKey, number>>({
    active: 1,
    done: 1,
    published: 1,
    failed: 1,
  });
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteConfirmTimer = useRef<number | null>(null);
  const deleteErrorTimer = useRef<number | null>(null);

  function fetchPage(group: GroupKey, page: number): Promise<DraftPage> {
    return api
      .get<DraftPage>(
        `/drafts?group=${group}&page=${page}&page_size=${PAGE_SIZE}`
      )
      .then((r) => r.data);
  }

  const active = useQuery({
    queryKey: ["drafts", "active", pages.active],
    queryFn: () => fetchPage("active", pages.active),
    refetchInterval: 5000,
  });
  const done = useQuery({
    queryKey: ["drafts", "done", pages.done],
    queryFn: () => fetchPage("done", pages.done),
  });
  const published = useQuery({
    queryKey: ["drafts", "published", pages.published],
    queryFn: () => fetchPage("published", pages.published),
  });
  const failed = useQuery({
    queryKey: ["drafts", "failed", pages.failed],
    queryFn: () => fetchPage("failed", pages.failed),
  });

  const queries: Record<GroupKey, typeof active> = {
    active,
    done,
    published,
    failed,
  };

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

  const deleteDraft = useMutation({
    mutationFn: async (id: string) => api.delete(`/drafts/${id}`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["drafts"] });
      qc.invalidateQueries({ queryKey: ["library"] });
      setDeleteConfirmId(null);
      setDeleteError(null);
    },
    onError: (err: unknown) => {
      setDeleteConfirmId(null);
      const status =
        typeof err === "object" && err !== null && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      const detail =
        typeof err === "object" && err !== null && "response" in err
          ? (err as { response?: { data?: { detail?: unknown } } }).response
              ?.data?.detail
          : undefined;
      const msg =
        typeof detail === "string"
          ? detail
          : status === 409
          ? "该草稿当前不允许删除"
          : status === 404
          ? "草稿不存在或已被删除"
          : "删除失败，请稍后重试";
      flashError(`${msg}${status ? ` (${status})` : ""}`);
    },
  });

  // Auto-rewind any group's page if its current page is now beyond last valid
  useEffect(() => {
    setPages((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const g of GROUPS) {
        const total = queries[g.key].data?.total;
        if (total === undefined) continue;
        const lastPage = Math.max(1, Math.ceil(total / PAGE_SIZE));
        if (next[g.key] > lastPage) {
          next[g.key] = lastPage;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
    // queries object is stable across renders — depend on each total directly
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    active.data?.total,
    done.data?.total,
    published.data?.total,
    failed.data?.total,
  ]);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (deleteConfirmTimer.current !== null) {
        window.clearTimeout(deleteConfirmTimer.current);
      }
      if (deleteErrorTimer.current !== null) {
        window.clearTimeout(deleteErrorTimer.current);
      }
    };
  }, []);

  function startDeleteConfirm(id: string) {
    setDeleteConfirmId(id);
    if (deleteConfirmTimer.current !== null) {
      window.clearTimeout(deleteConfirmTimer.current);
    }
    deleteConfirmTimer.current = window.setTimeout(() => {
      setDeleteConfirmId(null);
      deleteConfirmTimer.current = null;
    }, 5000);
  }

  function confirmDelete(id: string) {
    if (deleteConfirmTimer.current !== null) {
      window.clearTimeout(deleteConfirmTimer.current);
      deleteConfirmTimer.current = null;
    }
    deleteDraft.mutate(id);
  }

  function setGroupPage(g: GroupKey, p: number) {
    setPages((prev) => ({ ...prev, [g]: p }));
  }

  const allLoading = GROUPS.every((g) => queries[g.key].isLoading);
  const totalCount = GROUPS.reduce(
    (sum, g) => sum + (queries[g.key].data?.total ?? 0),
    0
  );
  const noData = !allLoading && totalCount === 0;

  return (
    <div className="page-shell">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">草稿</h1>
          <p className="text-page-subtitle">AI 改写后的文章草稿，点击进入编辑与推送</p>
        </div>

        {totalCount > 0 && (
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <span className="text-stat">{totalCount}</span>
            <EyebrowLabel
              style={{
                display: "block",
                marginTop: "var(--space-1)",
                textAlign: "right",
              }}
            >
              合计
            </EyebrowLabel>
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

      {allLoading ? (
        <PageSpinner />
      ) : noData ? (
        <EmptyState
          icon={
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect
                x="8"
                y="8"
                width="24"
                height="28"
                rx="3"
                stroke="currentColor"
                strokeWidth="1.5"
              />
              <path
                d="M14 16h12M14 21h12M14 26h8"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            </svg>
          }
          title="暂无草稿"
          description="在素材库选择文章并触发改写后，草稿将出现在这里"
        />
      ) : (
        <div className="ed-table">
          {GROUPS.map((g) => {
            const q = queries[g.key];
            const total = q.data?.total ?? 0;
            const items = q.data?.items ?? [];
            // Hide empty non-active groups to reduce noise
            if (total === 0 && g.key !== "active") return null;

            return (
              <div key={g.key} className="ed-table-group">
                <div className="ed-table-group-header">
                  <h2 className="ed-table-group-title">{g.label}</h2>
                  <span className="ed-table-group-count">{total}</span>
                </div>

                {items.length === 0 ? (
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
                  <>
                    {items.map((draft, localI) => {
                      const indexStr = String(
                        (pages[g.key] - 1) * PAGE_SIZE + localI + 1
                      ).padStart(2, "0");
                      const isConfirming = deleteConfirmId === draft.id;
                      const isDeleting =
                        deleteDraft.isPending &&
                        deleteDraft.variables === draft.id;

                      return (
                        <div
                          key={draft.id}
                          className="ed-row"
                          role="button"
                          tabIndex={0}
                          onClick={() => navigate(`/drafts/${draft.id}`)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter" || e.key === " ") {
                              e.preventDefault();
                              navigate(`/drafts/${draft.id}`);
                            }
                          }}
                          style={{
                            gridTemplateColumns: g.canDelete
                              ? "32px 1fr 90px 90px 28px 56px 16px"
                              : "32px 1fr 90px 90px 28px 16px",
                            cursor: "pointer",
                            animationDelay: `${localI * 30}ms`,
                            animation: `fade-in var(--dur-normal) ${
                              localI * 30
                            }ms var(--ease-out) both`,
                          }}
                        >
                          {/* Index */}
                          <span className="ed-row-index">{indexStr}</span>

                          {/* Title + optional error */}
                          <div style={{ minWidth: 0 }}>
                            <p className="ed-row-title" style={{ margin: 0 }}>
                              {draft.title ?? "（标题生成中…）"}
                            </p>
                            {draft.error_msg && (
                              <p
                                style={{
                                  margin: "var(--space-1) 0 0 0",
                                  fontSize: "var(--text-xs)",
                                  color: "var(--color-failed-fg)",
                                  lineHeight: "var(--leading-snug)",
                                }}
                              >
                                {draft.error_msg}
                              </p>
                            )}
                          </div>

                          {/* Created date */}
                          <span
                            className="ed-row-meta"
                            style={{ textAlign: "right" }}
                          >
                            {formatDate(draft.created_at)}
                          </span>

                          {/* Status badge */}
                          <div
                            style={{
                              display: "flex",
                              justifyContent: "flex-end",
                            }}
                          >
                            <Badge
                              variant={STATUS_BADGE[draft.status] ?? "default"}
                            >
                              {STATUS_LABEL[draft.status] ?? draft.status}
                            </Badge>
                          </div>

                          {/* Original source URL external link */}
                          <div
                            onClick={(e) => e.stopPropagation()}
                            style={{
                              display: "flex",
                              justifyContent: "center",
                              alignItems: "center",
                            }}
                          >
                            {draft.source_url ? (
                              <a
                                href={draft.source_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                title="查看原文"
                                aria-label="查看原文"
                                style={{
                                  display: "inline-flex",
                                  alignItems: "center",
                                  justifyContent: "center",
                                  width: "24px",
                                  height: "24px",
                                  borderRadius: "var(--radius-sm)",
                                  color: "var(--color-ink-3)",
                                  transition: "color var(--dur-fast), background var(--dur-fast)",
                                }}
                                onMouseEnter={(e) => {
                                  e.currentTarget.style.color = "var(--color-ink)";
                                  e.currentTarget.style.background =
                                    "var(--color-surface-2)";
                                }}
                                onMouseLeave={(e) => {
                                  e.currentTarget.style.color = "var(--color-ink-3)";
                                  e.currentTarget.style.background = "transparent";
                                }}
                              >
                                <svg
                                  width="14"
                                  height="14"
                                  viewBox="0 0 16 16"
                                  fill="none"
                                  stroke="currentColor"
                                  strokeWidth="1.5"
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                >
                                  <path d="M7 3H3v10h10V9" />
                                  <path d="M9 2h5v5" />
                                  <path d="M14 2L7 9" />
                                </svg>
                              </a>
                            ) : (
                              <span aria-hidden style={{ width: "24px" }} />
                            )}
                          </div>

                          {/* Delete button — only on canDelete groups */}
                          {g.canDelete && (
                            <div
                              onClick={(e) => e.stopPropagation()}
                              style={{
                                display: "flex",
                                justifyContent: "flex-end",
                              }}
                            >
                              {isConfirming ? (
                                <button
                                  type="button"
                                  onClick={() => confirmDelete(draft.id)}
                                  disabled={isDeleting}
                                  style={{
                                    background: "none",
                                    border: "none",
                                    padding: 0,
                                    fontSize: "var(--text-xs)",
                                    color: "var(--color-failed-fg)",
                                    cursor: isDeleting
                                      ? "not-allowed"
                                      : "pointer",
                                    fontWeight: "var(--weight-semi)",
                                    textDecoration: "underline",
                                  }}
                                >
                                  确认？
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() =>
                                    startDeleteConfirm(draft.id)
                                  }
                                  disabled={isDeleting}
                                  style={{
                                    background: "none",
                                    border: "none",
                                    padding: 0,
                                    fontSize: "var(--text-xs)",
                                    color: "var(--color-failed-fg)",
                                    cursor: isDeleting
                                      ? "not-allowed"
                                      : "pointer",
                                    textDecoration: "underline",
                                  }}
                                >
                                  删除
                                </button>
                              )}
                            </div>
                          )}

                          {/* Arrow */}
                          <span className="ed-row-arrow">
                            <ChevronRight />
                          </span>
                        </div>
                      );
                    })}

                    <Pager
                      page={pages[g.key]}
                      total={total}
                      onChange={(p) => setGroupPage(g.key, p)}
                    />
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
