import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge, EmptyState, EyebrowLabel, PageSpinner } from "../components/ui";

type Draft = {
  id: string;
  title: string | null;
  status: string;
  error_msg: string | null;
  review_report_id: string | null;
  created_at: string;
};

type DraftStatus =
  | "pending"
  | "writing"
  | "reviewing"
  | "done"
  | "failed"
  | "published_to_wechat";

const STATUS_BADGE: Record<string, "pending" | "processing" | "done" | "failed" | "warn"> = {
  pending: "pending",
  writing: "processing",
  reviewing: "processing",
  done: "done",
  failed: "failed",
  published_to_wechat: "done",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "待处理",
  writing: "改写中",
  reviewing: "审核中",
  done: "完成",
  failed: "失败",
  published_to_wechat: "已推送",
};

// Group definitions — order matters
const GROUPS: {
  key: string;
  label: string;
  statuses: string[];
}[] = [
  { key: "active", label: "进行中", statuses: ["pending", "writing", "reviewing"] },
  { key: "done", label: "待推送", statuses: ["done"] },
  { key: "published", label: "已推送", statuses: ["published_to_wechat"] },
  { key: "failed", label: "失败", statuses: ["failed"] },
];

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Chevron arrow icon
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

export default function Drafts() {
  const { data, isLoading } = useQuery({
    queryKey: ["drafts"],
    queryFn: async () => (await api.get<Draft[]>("/drafts")).data,
    refetchInterval: 5000,
  });

  const totalCount = data?.length ?? 0;

  // Build groups
  const groups = GROUPS.map((g) => ({
    ...g,
    items: (data ?? []).filter((d) => g.statuses.includes(d.status)),
  })).filter((g) => {
    // Always show active/done/published; only show failed if there are failures
    if (g.key === "failed") return g.items.length > 0;
    return true;
  });

  // Running start index per group (precomputed so JSX stays pure)
  const groupStartIndices = groups.reduce<number[]>((acc, g, i) => {
    acc.push(i === 0 ? 0 : acc[i - 1] + groups[i - 1].items.length);
    return acc;
  }, []);

  return (
    <div className="page-shell">
      {/* Page header */}
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">草稿</h1>
          <p className="text-page-subtitle">AI 改写后的文章草稿，点击进入编辑与推送</p>
        </div>

        {/* Total count stat */}
        {totalCount > 0 && (
          <div style={{ textAlign: "right", flexShrink: 0 }}>
            <span className="text-stat">{totalCount}</span>
            <EyebrowLabel style={{ display: "block", marginTop: "var(--space-1)", textAlign: "right" }}>
              合计
            </EyebrowLabel>
          </div>
        )}
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect x="8" y="8" width="24" height="28" rx="3" stroke="currentColor" strokeWidth="1.5" />
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
          {groups.map((group, groupIdx) => {
            const groupStartIndex = groupStartIndices[groupIdx];
            return (
              <div key={group.key} className="ed-table-group">
                {/* Group header */}
                <div className="ed-table-group-header">
                  <h2 className="ed-table-group-title">{group.label}</h2>
                  <span className="ed-table-group-count">{group.items.length}</span>
                </div>

                {/* Rows */}
                {group.items.length === 0 ? (
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
                  group.items.map((draft, localI) => {
                    const rowIndex = groupStartIndex + localI;
                    const indexStr = String(rowIndex + 1).padStart(2, "0");
                    return (
                      <Link
                        key={draft.id}
                        to={`/drafts/${draft.id}`}
                        className="ed-row"
                        style={{
                          gridTemplateColumns: "32px 1fr 90px 90px 16px",
                          animationDelay: `${localI * 30}ms`,
                          animation: `fade-in var(--dur-normal) ${localI * 30}ms var(--ease-out) both`,
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
                        <span className="ed-row-meta" style={{ textAlign: "right" }}>
                          {formatDate(draft.created_at)}
                        </span>

                        {/* Status badge */}
                        <div style={{ display: "flex", justifyContent: "flex-end" }}>
                          <Badge
                            variant={STATUS_BADGE[draft.status as DraftStatus] ?? "default"}
                          >
                            {STATUS_LABEL[draft.status] ?? draft.status}
                          </Badge>
                        </div>

                        {/* Arrow */}
                        <span className="ed-row-arrow">
                          <ChevronRight />
                        </span>
                      </Link>
                    );
                  })
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
