import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";

const SANITIZE_CONFIG = {
  ALLOWED_TAGS: ["p", "strong", "em", "br", "h1", "h2", "h3", "img", "a", "ul", "ol", "li", "blockquote"],
  ALLOWED_ATTR: ["src", "alt", "href", "title"],
};
import {
  Badge,
  Button,
  EyebrowLabel,
  HairlineMeter,
  HairlineRule,
  PageSpinner,
  ScoreDial,
  ScoreNumber,
} from "../components/ui";

type Detail = {
  id: string;
  title: string | null;
  content_html: string | null;
  status: string;
  review_report_id: string | null;
  error_msg: string | null;
  regenerate_count: number;
  max_regenerations: number;
  source_url: string | null;
  original_title: string | null;
  original_author: string | null;
  original_content_text: string | null;
};

type PushBanner =
  | { kind: "info"; msg: string }
  | { kind: "success"; msg: string }
  | { kind: "error"; msg: string };

function extractErrorDetail(err: unknown): string | null {
  if (typeof err !== "object" || err === null) return null;
  const data = (err as { response?: { data?: { detail?: unknown } } }).response
    ?.data?.detail;
  return typeof data === "string" ? data : null;
}

type DimBlock = {
  score?: number;
  issues?: string[];
  similarity?: number;
};

type Report = {
  compliance: DimBlock | null;
  originality: DimBlock | null;
  quality: DimBlock | null;
  clickbait: DimBlock | null;
  overall_score: number | null;
};

type Img = {
  id: string;
  original_url: string;
  wechat_url: string | null;
  status: string;
  is_cover: boolean;
  error_msg: string | null;
};

type DimKey = "compliance" | "originality" | "quality" | "clickbait";

const DIMS: { key: DimKey; label: string; description: string }[] = [
  { key: "compliance", label: "合规", description: "内容合规性" },
  { key: "originality", label: "原创度", description: "文章独创性" },
  { key: "quality", label: "质量", description: "内容质量" },
  { key: "clickbait", label: "标题党", description: "标题诱导程度" },
];

const STATUS_LABEL: Record<string, string> = {
  draft: "改写中",
  reviewing: "审核中",
  reviewed: "待推送",
  failed: "失败",
  published_to_wechat: "已推送",
};

interface IssueQuotesProps {
  issues: string[];
  expanded: boolean;
  onToggle: () => void;
}

function IssueQuotes({ issues, expanded, onToggle }: IssueQuotesProps) {
  const initialLimit = 2;
  const showAll = expanded || issues.length <= initialLimit;
  const visible = showAll ? issues : issues.slice(0, initialLimit);
  const remaining = issues.length - initialLimit;
  return (
    <div
      style={{
        marginTop: "var(--space-2)",
        display: "flex",
        flexDirection: "column",
        gap: "var(--space-1)",
      }}
    >
      {visible.map((it, i) => (
        <p
          key={i}
          style={{
            margin: 0,
            fontSize: "var(--text-xs)",
            fontStyle: "italic",
            color: "var(--color-ink-2)",
            lineHeight: "var(--leading-snug)",
            paddingLeft: "0.9em",
            textIndent: "-0.9em",
          }}
        >
          <span style={{ color: "var(--color-ink-3)", marginRight: "0.3em", fontStyle: "normal" }}>—</span>
          {it}
        </p>
      ))}
      {remaining > 0 && !expanded && (
        <button
          onClick={onToggle}
          style={{
            alignSelf: "flex-start",
            background: "none",
            border: "none",
            padding: 0,
            marginTop: "var(--space-1)",
            fontSize: "var(--text-xs)",
            color: "var(--color-ink-3)",
            cursor: "pointer",
            textDecoration: "underline",
            textDecorationStyle: "dotted",
            textUnderlineOffset: "2px",
          }}
        >
          +{remaining} more
        </button>
      )}
      {expanded && issues.length > initialLimit && (
        <button
          onClick={onToggle}
          style={{
            alignSelf: "flex-start",
            background: "none",
            border: "none",
            padding: 0,
            marginTop: "var(--space-1)",
            fontSize: "var(--text-xs)",
            color: "var(--color-ink-3)",
            cursor: "pointer",
            textDecoration: "underline",
            textDecorationStyle: "dotted",
            textUnderlineOffset: "2px",
          }}
        >
          collapse
        </button>
      )}
    </div>
  );
}

function wordCount(html: string): number {
  const text = html.replace(/<[^>]*>/g, "");
  return text.replace(/\s+/g, "").length;
}

export default function DraftDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const [pushBanner, setPushBanner] = useState<PushBanner | null>(null);
  const [pollingForPublish, setPollingForPublish] = useState(false);

  const detail = useQuery({
    queryKey: ["draft", id],
    queryFn: async () => (await api.get<Detail>(`/drafts/${id}`)).data,
    refetchInterval: pollingForPublish ? 2000 : false,
  });

  const report = useQuery({
    queryKey: ["draft-report", id],
    queryFn: async () => (await api.get<Report>(`/drafts/${id}/report`)).data,
    enabled: Boolean(detail.data?.review_report_id),
  });

  const images = useQuery({
    queryKey: ["draft-images", id],
    queryFn: async () => (await api.get<Img[]>(`/images/by-draft/${id}`)).data,
    refetchInterval: 5000,
  });

  const setCover = useMutation({
    mutationFn: async (imgId: string) => api.post(`/images/${imgId}/cover`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
  });

  const removeImg = useMutation({
    mutationFn: async (imgId: string) => api.delete(`/images/${imgId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
  });

  const publish = useMutation({
    mutationFn: async () => api.post(`/drafts/${id}/publish-to-wechat`),
    onMutate: () => {
      setPushBanner({
        kind: "info",
        msg: "已加入推送队列,正在上传图片并推送至微信草稿箱…",
      });
    },
    onSuccess: () => {
      setPollingForPublish(true);
      qc.invalidateQueries({ queryKey: ["draft", id] });
    },
    onError: (err: unknown) => {
      setPollingForPublish(false);
      const detail = extractErrorDetail(err);
      setPushBanner({
        kind: "error",
        msg: `推送请求失败:${detail ?? "请稍后重试"}`,
      });
    },
  });

  const rewriteAgain = useMutation({
    mutationFn: async () => api.post(`/drafts/${id}/rewrite`),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["draft", id] });
      qc.invalidateQueries({ queryKey: ["draft-report", id] });
      qc.invalidateQueries({ queryKey: ["draft-images", id] });
    },
  });

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");
  const [showOriginal, setShowOriginal] = useState(false);
  const [expandedDims, setExpandedDims] = useState<Set<DimKey>>(new Set());
  const [savedIndicator, setSavedIndicator] = useState(false);

  function toggleDim(key: DimKey) {
    setExpandedDims((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  useEffect(() => {
    if (detail.data) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync local form draft state with async-loaded server data; resets when navigating to a different draft
      setTitle(detail.data.title ?? "");
      setBody(detail.data.content_html ?? "");
    }
  }, [detail.data]);

  // While polling after a publish click, react to terminal status changes.
  useEffect(() => {
    if (!pollingForPublish || !detail.data) return;
    const status = detail.data.status;
    if (status === "published_to_wechat") {
      setPushBanner({
        kind: "success",
        msg: "✓ 已成功推送至微信草稿箱,可在公众号后台查看",
      });
      setPollingForPublish(false);
      const t = window.setTimeout(() => setPushBanner(null), 6000);
      return () => window.clearTimeout(t);
    }
    if (status === "failed") {
      setPushBanner({
        kind: "error",
        msg: `推送失败:${detail.data.error_msg ?? "未知错误,请查看后端日志"}`,
      });
      setPollingForPublish(false);
    }
  }, [pollingForPublish, detail.data]);

  const save = useMutation({
    mutationFn: async () =>
      api.patch(`/drafts/${id}`, { title, content_html: body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["draft", id] });
      setSavedIndicator(true);
      setTimeout(() => setSavedIndicator(false), 2000);
    },
  });

  const isPublished = detail.data?.status === "published_to_wechat";
  const canPublish = detail.data?.status === "reviewed";
  const charCount = wordCount(body);
  const safeBody = useMemo(() => DOMPurify.sanitize(body, SANITIZE_CONFIG), [body]);

  if (!detail.data) return <PageSpinner />;

  const truncatedTitle =
    title.length > 30 ? title.slice(0, 30) + "…" : title || "无标题";

  return (
    <div
      className="page-shell page-shell-wide"
      style={{ paddingBottom: "var(--space-20)" }}
    >
      {/* Meta strip — breadcrumb + word count + saved indicator */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: "var(--space-4)",
          marginBottom: "var(--space-6)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "var(--space-2)",
          }}
        >
          <Link
            to="/drafts"
            className="mono"
            style={{
              color: "var(--color-ink-3)",
              textDecoration: "none",
              transition: "color var(--dur-fast)",
            }}
            onMouseEnter={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "var(--color-ink)"; }}
            onMouseLeave={(e) => { (e.currentTarget as HTMLAnchorElement).style.color = "var(--color-ink-3)"; }}
          >
            草稿
          </Link>
          <span className="mono" style={{ color: "var(--color-ink-4)" }}>/</span>
          <span className="mono" style={{ color: "var(--color-ink-2)" }}>
            {truncatedTitle}
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "var(--space-4)" }}>
          {savedIndicator && (
            <span
              style={{
                fontSize: "var(--text-xs)",
                color: "var(--color-done-fg)",
                fontFamily: "var(--font-mono)",
                animation: "fade-in var(--dur-fast) var(--ease-out) both",
              }}
            >
              已保存
            </span>
          )}
          <span
            className="mono"
            style={{ color: "var(--color-ink-4)" }}
          >
            正文 {charCount.toLocaleString()} 字
          </span>
        </div>
      </div>

      <HairlineRule style={{ marginBottom: "var(--space-8)" }} />

      {/* Two-column grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: showOriginal
            ? "minmax(0, 0.4fr) minmax(0, 0.6fr) 360px"
            : "1fr 360px",
          gap: "var(--space-6)",
          alignItems: "start",
        }}
      >
        {/* LEFT-LEFT — original article panel (slides in when showOriginal) */}
        {showOriginal && (
          <aside
            style={{
              display: "flex",
              flexDirection: "column",
              gap: "var(--space-3)",
              padding: "var(--space-5)",
              background: "var(--color-surface-2)",
              borderRadius: "var(--radius-md)",
              minHeight: "60vh",
              maxHeight: "calc(100vh - 200px)",
              overflow: "auto",
              position: "sticky",
              top: "var(--space-4)",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <EyebrowLabel>原文</EyebrowLabel>
              <button
                type="button"
                onClick={() => setShowOriginal(false)}
                aria-label="收起原文"
                title="收起原文"
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  color: "var(--color-ink-3)",
                  fontSize: "var(--text-sm)",
                  padding: "var(--space-1)",
                }}
              >
                ✕
              </button>
            </div>
            <h2
              className="text-section-title"
              style={{
                margin: 0,
                fontSize: "var(--text-lg)",
                lineHeight: "var(--leading-snug)",
              }}
            >
              {detail.data.original_title ?? "（原标题未抓取）"}
            </h2>
            <div
              style={{
                display: "flex",
                gap: "var(--space-3)",
                alignItems: "center",
                fontSize: "var(--text-xs)",
                color: "var(--color-ink-3)",
                flexWrap: "wrap",
              }}
            >
              {detail.data.original_author && (
                <span>{detail.data.original_author}</span>
              )}
              {detail.data.source_url && (
                <a
                  href={detail.data.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    color: "var(--color-ink-2)",
                    textDecoration: "underline",
                    textDecorationStyle: "dotted",
                    textUnderlineOffset: "2px",
                  }}
                >
                  原文链接 ↗
                </a>
              )}
            </div>
            <div
              style={{
                fontSize: "var(--text-base)",
                lineHeight: "var(--leading-loose)",
                color: "var(--color-ink-2)",
                whiteSpace: "pre-wrap",
                wordBreak: "break-word",
              }}
            >
              {detail.data.original_content_text ? (
                detail.data.original_content_text
                  .split(/\n{2,}/)
                  .filter((p) => p.trim().length > 0)
                  .map((para, i) => (
                    <p
                      key={i}
                      style={{
                        margin: "0 0 var(--space-3) 0",
                      }}
                    >
                      {para}
                    </p>
                  ))
              ) : (
                <p style={{ color: "var(--color-ink-3)", fontStyle: "italic" }}>
                  （原文正文未抓取）
                </p>
              )}
            </div>
          </aside>
        )}

        {/* LEFT — editor */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>
          {/* Editorial title input */}
          <div>
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="文章标题"
              className="text-editorial-title"
              style={{
                width: "100%",
                background: "none",
                border: "none",
                borderBottom: "1px dashed var(--color-surface-3)",
                outline: "none",
                padding: "var(--space-2) 0",
                boxSizing: "border-box",
                transition: "border-color var(--dur-fast)",
                display: "block",
              }}
              onFocus={(e) => {
                e.currentTarget.style.borderBottomColor = "var(--color-ink)";
              }}
              onBlur={(e) => {
                e.currentTarget.style.borderBottomColor = "var(--color-surface-3)";
              }}
            />
          </div>

          {/* Edit / Preview tabs */}
          <div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                borderBottom: "1px solid var(--color-surface-3)",
                marginBottom: "var(--space-4)",
              }}
            >
              {(["edit", "preview"] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  style={{
                    padding: "var(--space-2) var(--space-4)",
                    fontSize: "var(--text-sm)",
                    fontWeight: activeTab === tab ? "var(--weight-medium)" : "var(--weight-normal)",
                    color: activeTab === tab ? "var(--color-ink)" : "var(--color-ink-3)",
                    background: "none",
                    border: "none",
                    borderBottom: activeTab === tab ? "2px solid var(--color-ink)" : "2px solid transparent",
                    cursor: "pointer",
                    marginBottom: "-1px",
                    transition: "color var(--dur-fast)",
                  }}
                >
                  {tab === "edit" ? "编辑" : "预览"}
                </button>
              ))}
              <button
                type="button"
                onClick={() => setShowOriginal((v) => !v)}
                style={{
                  marginLeft: "auto",
                  padding: "var(--space-1) var(--space-3)",
                  fontSize: "var(--text-xs)",
                  color: showOriginal ? "var(--color-ink)" : "var(--color-ink-3)",
                  background: showOriginal ? "var(--color-surface-2)" : "none",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-sm)",
                  cursor: "pointer",
                  marginBottom: "var(--space-1)",
                  transition: "all var(--dur-fast)",
                }}
                title={showOriginal ? "收起原文" : "对比原文"}
              >
                {showOriginal ? "✕ 隐藏原文" : "« 对比原文"}
              </button>
            </div>

            {activeTab === "edit" ? (
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="input-base input-mono"
                style={{
                  minHeight: "60vh",
                  resize: "vertical",
                  lineHeight: "var(--leading-loose)",
                  border: "none",
                  backgroundColor: "var(--color-surface-2)",
                  padding: "var(--space-5)",
                  borderRadius: "var(--radius-md)",
                }}
              />
            ) : (
              <div
                className="prose-preview"
                style={{
                  minHeight: "60vh",
                  padding: "var(--space-6)",
                  backgroundColor: "var(--color-white)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                }}
                dangerouslySetInnerHTML={{ __html: safeBody }}
              />
            )}
          </div>

          {/* Image review */}
          {images.data && images.data.length > 0 && (
            <section>
              <EyebrowLabel
                as="h2"
                style={{ color: "var(--color-ink)", margin: "0 0 var(--space-4) 0" }}
              >
                图片复核
              </EyebrowLabel>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))",
                  gap: "var(--space-3)",
                }}
              >
                {images.data.map((img) => (
                  <div
                    key={img.id}
                    className="surface-panel"
                    style={{
                      overflow: "hidden",
                      border: `2px solid ${img.is_cover ? "var(--color-ink)" : "var(--color-surface-3)"}`,
                      transition: "border-color var(--dur-fast)",
                    }}
                  >
                    <img
                      src={img.wechat_url ?? img.original_url}
                      alt=""
                      style={{
                        width: "100%",
                        height: "100px",
                        objectFit: "cover",
                        display: "block",
                      }}
                    />
                    <div style={{ padding: "var(--space-2) var(--space-3)" }}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: "var(--space-2)",
                          marginBottom: "var(--space-2)",
                        }}
                      >
                        <Badge
                          variant={
                            img.status === "uploaded" || img.status === "replaced"
                              ? "done"
                              : img.status === "failed"
                              ? "failed"
                              : "processing"
                          }
                        >
                          {img.status}
                        </Badge>
                        {img.is_cover && <Badge variant="default">封面</Badge>}
                      </div>
                      {img.error_msg && (
                        <p
                          style={{
                            fontSize: "var(--text-xs)",
                            color: "var(--color-failed-fg)",
                            margin: "0 0 var(--space-2) 0",
                          }}
                        >
                          {img.error_msg}
                        </p>
                      )}
                      <div style={{ display: "flex", gap: "var(--space-2)" }}>
                        <button
                          onClick={() => setCover.mutate(img.id)}
                          disabled={img.is_cover}
                          style={{
                            fontSize: "var(--text-xs)",
                            color: img.is_cover ? "var(--color-ink-4)" : "var(--color-link)",
                            background: "none",
                            border: "none",
                            cursor: img.is_cover ? "default" : "pointer",
                            padding: 0,
                            textDecoration: "underline",
                          }}
                        >
                          设封面
                        </button>
                        <button
                          onClick={() => removeImg.mutate(img.id)}
                          style={{
                            fontSize: "var(--text-xs)",
                            color: "var(--color-failed-fg)",
                            background: "none",
                            border: "none",
                            cursor: "pointer",
                            padding: 0,
                            textDecoration: "underline",
                          }}
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {/* RIGHT — sticky sidebar */}
        <div
          style={{
            position: "sticky",
            top: "var(--space-8)",
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
          }}
        >
          {/* Review report */}
          {report.data && (
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
              {/* Score dial block */}
              <div>
                <EyebrowLabel style={{ textAlign: "center", display: "block", marginBottom: "var(--space-3)" }}>
                  OVERALL SCORE
                </EyebrowLabel>
                <div style={{ display: "flex", justifyContent: "center" }}>
                  <ScoreDial score={report.data.overall_score ?? undefined} size={96} />
                </div>
                <p
                  className="mono"
                  style={{
                    textAlign: "center",
                    marginTop: "var(--space-2)",
                    letterSpacing: "0.02em",
                  }}
                >
                  4 dimensions reviewed
                </p>
                <HairlineRule style={{ marginTop: "var(--space-3)" }} />
              </div>

              {/* 4 dimensions */}
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
                {DIMS.map((d) => {
                  const block = report.data![d.key] as DimBlock | null;
                  const expanded = expandedDims.has(d.key);
                  return (
                    <div key={d.key}>
                      <div
                        style={{
                          display: "flex",
                          alignItems: "baseline",
                          justifyContent: "space-between",
                          gap: "var(--space-3)",
                        }}
                      >
                        <EyebrowLabel>{d.label}</EyebrowLabel>
                        <ScoreNumber score={block?.score} size="md" />
                      </div>
                      <HairlineMeter score={block?.score} style={{ marginTop: "var(--space-2)" }} />
                      {block?.issues && block.issues.length > 0 && (
                        <IssueQuotes
                          issues={block.issues}
                          expanded={expanded}
                          onToggle={() => toggleDim(d.key)}
                        />
                      )}
                    </div>
                  );
                })}
              </div>

              <HairlineRule />
            </div>
          )}

          {/* Status indicator */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <EyebrowLabel>状态</EyebrowLabel>
            <Badge
              variant={
                detail.data.status === "reviewed" || detail.data.status === "published_to_wechat"
                  ? "done"
                  : detail.data.status === "failed"
                  ? "failed"
                  : "processing"
              }
            >
              {STATUS_LABEL[detail.data.status] ?? detail.data.status}
            </Badge>
          </div>
        </div>
      </div>

      {/* Push-to-wechat status banner — sits above the action bar */}
      {pushBanner && (
        <div
          role="alert"
          style={{
            position: "fixed",
            bottom: "calc(var(--space-6) + 80px)",
            left: "calc(var(--sidebar-width) + var(--space-6))",
            right: "var(--space-6)",
            margin: "0 auto",
            maxWidth: "720px",
            padding: "var(--space-3) var(--space-4)",
            borderRadius: "var(--radius-lg)",
            boxShadow: "var(--shadow-md)",
            backgroundColor:
              pushBanner.kind === "success"
                ? "var(--color-done)"
                : pushBanner.kind === "error"
                ? "var(--color-failed)"
                : "var(--color-ink)",
            color:
              pushBanner.kind === "success"
                ? "var(--color-done-fg)"
                : pushBanner.kind === "error"
                ? "var(--color-failed-fg)"
                : "var(--color-accent-fg)",
            display: "flex",
            alignItems: "center",
            gap: "var(--space-3)",
            fontSize: "var(--text-sm)",
            zIndex: 31,
            animation: "slide-up var(--dur-slow) var(--ease-out) both",
          }}
        >
          {pushBanner.kind === "info" && (
            <span
              aria-hidden
              style={{
                width: 12,
                height: 12,
                borderRadius: "50%",
                border: "2px solid currentColor",
                borderTopColor: "transparent",
                animation: "spin 0.8s linear infinite",
                flexShrink: 0,
              }}
            />
          )}
          <span style={{ flex: 1 }}>{pushBanner.msg}</span>
          <button
            type="button"
            aria-label="关闭"
            onClick={() => setPushBanner(null)}
            style={{
              background: "none",
              border: "none",
              color: "inherit",
              cursor: "pointer",
              fontSize: "var(--text-xs)",
              textDecoration: "underline",
              padding: 0,
              flexShrink: 0,
            }}
          >
            关闭
          </button>
        </div>
      )}

      {/* Persistent bottom action bar */}
      <div className="action-bar">
        <span
          className="mono"
          style={{ color: "rgba(255,255,255,0.6)", flexShrink: 0 }}
        >
          正文 {charCount.toLocaleString()} 字
        </span>

        <div style={{ flex: 1 }} />

        <Button
          variant="secondary"
          onClick={() => save.mutate()}
          loading={save.isPending}
          style={{
            backgroundColor: "rgba(255,255,255,0.12)",
            color: "var(--color-white)",
            border: "1px solid rgba(255,255,255,0.2)",
            flexShrink: 0,
          }}
        >
          {save.isPending ? "保存中…" : "保存草稿"}
        </Button>

        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm("将清空当前标题、正文、评审报告和图片,重新改写。是否继续?")) {
              rewriteAgain.mutate();
            }
          }}
          disabled={
            rewriteAgain.isPending ||
            detail.data.status === "draft" ||
            detail.data.status === "reviewing" ||
            detail.data.status === "published_to_wechat" ||
            detail.data.regenerate_count >= detail.data.max_regenerations
          }
          loading={rewriteAgain.isPending}
          style={{
            backgroundColor: "rgba(255,255,255,0.12)",
            color: "var(--color-white)",
            border: "1px solid rgba(255,255,255,0.2)",
            flexShrink: 0,
          }}
        >
          {rewriteAgain.isPending
            ? "重写中…"
            : `重新改写 (${detail.data.regenerate_count}/${detail.data.max_regenerations})`}
        </Button>

        <Button
          variant="primary"
          onClick={() => publish.mutate()}
          disabled={!canPublish || isPublished}
          loading={publish.isPending}
          style={{ flexShrink: 0 }}
        >
          {isPublished
            ? "已推送至微信"
            : publish.isPending
            ? "推送中…"
            : !canPublish
            ? "等待审核完成"
            : "推送到微信草稿箱"}
        </Button>
      </div>
    </div>
  );
}
