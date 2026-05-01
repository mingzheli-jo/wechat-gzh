import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import { Badge, EmptyState, PageSpinner } from "../components/ui";

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

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function Drafts() {
  const { data, isLoading } = useQuery({
    queryKey: ["drafts"],
    queryFn: async () => (await api.get<Draft[]>("/drafts")).data,
    refetchInterval: 5000,
  });

  return (
    <div
      style={{
        maxWidth: "var(--max-content)",
        margin: "0 auto",
        padding: "var(--space-8)",
      }}
    >
      {/* Page header */}
      <div style={{ marginBottom: "var(--space-8)" }}>
        <h1
          style={{
            fontSize: "var(--text-xl)",
            fontWeight: "var(--weight-semi)",
            color: "var(--color-ink)",
            letterSpacing: "-0.02em",
            margin: 0,
          }}
        >
          草稿
        </h1>
        <p
          style={{
            fontSize: "var(--text-sm)",
            color: "var(--color-ink-3)",
            marginTop: "var(--space-1)",
          }}
        >
          AI 改写后的文章草稿，点击进入编辑与推送
        </p>
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
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(320px, 1fr))",
            gap: "var(--space-4)",
          }}
        >
          {data.map((draft, i) => (
            <Link
              key={draft.id}
              to={`/drafts/${draft.id}`}
              style={{
                display: "block",
                textDecoration: "none",
                animation: `fade-in var(--dur-normal) ${i * 40}ms var(--ease-out) both`,
              }}
            >
              <div
                style={{
                  backgroundColor: "var(--color-white)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-lg)",
                  padding: "var(--space-5)",
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  gap: "var(--space-3)",
                  transition: "border-color var(--dur-fast), box-shadow var(--dur-fast)",
                }}
                onMouseEnter={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = "var(--color-surface-4)";
                  (e.currentTarget as HTMLDivElement).style.boxShadow = "var(--shadow-md)";
                }}
                onMouseLeave={(e) => {
                  (e.currentTarget as HTMLDivElement).style.borderColor = "var(--color-surface-3)";
                  (e.currentTarget as HTMLDivElement).style.boxShadow = "none";
                }}
              >
                {/* Title row */}
                <div style={{ flex: 1 }}>
                  <p
                    style={{
                      fontSize: "var(--text-base)",
                      fontWeight: "var(--weight-medium)",
                      color: "var(--color-ink)",
                      margin: 0,
                      lineHeight: "var(--leading-snug)",
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {draft.title ?? "（标题生成中…）"}
                  </p>
                </div>

                {/* Error */}
                {draft.error_msg && (
                  <p
                    style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--color-failed-fg)",
                      margin: 0,
                    }}
                  >
                    {draft.error_msg}
                  </p>
                )}

                {/* Footer */}
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    borderTop: "1px solid var(--color-surface-2)",
                    paddingTop: "var(--space-3)",
                    marginTop: "auto",
                  }}
                >
                  <span
                    style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--color-ink-3)",
                    }}
                  >
                    {formatDate(draft.created_at)}
                  </span>
                  <Badge
                    variant={
                      STATUS_BADGE[draft.status as DraftStatus] ?? "default"
                    }
                  >
                    {STATUS_LABEL[draft.status] ?? draft.status}
                  </Badge>
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
