import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../api/client";
import { Badge, Button, Card, EyebrowLabel, PageSpinner, ScoreNumber } from "../components/ui";

type Detail = {
  id: string;
  title: string | null;
  content_html: string | null;
  status: string;
  review_report_id: string | null;
};

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

const DIMS: { key: keyof Report; label: string; description: string }[] = [
  { key: "compliance", label: "合规", description: "内容合规性" },
  { key: "originality", label: "原创度", description: "文章独创性" },
  { key: "quality", label: "质量", description: "内容质量" },
  { key: "clickbait", label: "标题党", description: "标题诱导程度" },
];

export default function DraftDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const detail = useQuery({
    queryKey: ["draft", id],
    queryFn: async () => (await api.get<Detail>(`/drafts/${id}`)).data,
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
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
  });

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [activeTab, setActiveTab] = useState<"edit" | "preview">("edit");

  useEffect(() => {
    if (detail.data) {
      setTitle(detail.data.title ?? "");
      setBody(detail.data.content_html ?? "");
    }
  }, [detail.data]);

  const save = useMutation({
    mutationFn: async () =>
      api.patch(`/drafts/${id}`, { title, content_html: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
  });

  const isPublished = detail.data?.status === "published_to_wechat";

  if (!detail.data) return <PageSpinner />;

  return (
    <div
      style={{
        maxWidth: "var(--max-content)",
        margin: "0 auto",
        padding: "var(--space-8)",
        display: "grid",
        gridTemplateColumns: "1fr 320px",
        gap: "var(--space-8)",
        alignItems: "start",
      }}
    >
      {/* Main editor column */}
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-6)" }}>

        {/* Title input */}
        <div>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="文章标题"
            style={{
              width: "100%",
              fontSize: "var(--text-2xl)",
              fontWeight: "var(--weight-semi)",
              color: "var(--color-ink)",
              letterSpacing: "-0.02em",
              background: "none",
              border: "none",
              borderBottom: "2px solid var(--color-surface-3)",
              outline: "none",
              padding: "var(--space-2) 0",
              lineHeight: "var(--leading-snug)",
              transition: "border-color var(--dur-fast)",
              boxSizing: "border-box",
            }}
            onFocus={(e) => { e.currentTarget.style.borderBottomColor = "var(--color-ink)"; }}
            onBlur={(e) => { e.currentTarget.style.borderBottomColor = "var(--color-surface-3)"; }}
          />
        </div>

        {/* Edit / Preview tabs */}
        <div>
          <div
            style={{
              display: "flex",
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
          </div>

          {activeTab === "edit" ? (
            <textarea
              value={body}
              onChange={(e) => setBody(e.target.value)}
              style={{
                width: "100%",
                minHeight: "480px",
                padding: "var(--space-4)",
                fontSize: "var(--text-sm)",
                fontFamily: "var(--font-mono)",
                color: "var(--color-ink)",
                backgroundColor: "var(--color-surface-2)",
                border: "1px solid var(--color-surface-3)",
                borderRadius: "var(--radius-md)",
                outline: "none",
                resize: "vertical",
                lineHeight: "var(--leading-loose)",
                transition: "border-color var(--dur-fast)",
                boxSizing: "border-box",
              }}
              onFocus={(e) => { e.currentTarget.style.borderColor = "var(--color-ink)"; e.currentTarget.style.backgroundColor = "var(--color-white)"; }}
              onBlur={(e) => { e.currentTarget.style.borderColor = "var(--color-surface-3)"; e.currentTarget.style.backgroundColor = "var(--color-surface-2)"; }}
            />
          ) : (
            <div
              className="prose-preview"
              style={{
                minHeight: "480px",
                padding: "var(--space-6)",
                backgroundColor: "var(--color-white)",
                border: "1px solid var(--color-surface-3)",
                borderRadius: "var(--radius-md)",
              }}
              dangerouslySetInnerHTML={{ __html: body }}
            />
          )}

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "var(--space-3)",
              marginTop: "var(--space-3)",
            }}
          >
            <Button
              onClick={() => save.mutate()}
              loading={save.isPending}
              variant="secondary"
            >
              {save.isPending ? "保存中…" : "保存草稿"}
            </Button>
            {save.isSuccess && (
              <span style={{ fontSize: "var(--text-xs)", color: "var(--color-done-fg)" }}>
                已保存
              </span>
            )}
          </div>
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
                  style={{
                    backgroundColor: "var(--color-white)",
                    border: `2px solid ${img.is_cover ? "var(--color-ink)" : "var(--color-surface-3)"}`,
                    borderRadius: "var(--radius-md)",
                    overflow: "hidden",
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
                    <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
                      <Badge variant={img.status === "done" ? "done" : img.status === "failed" ? "failed" : "processing"}>
                        {img.status}
                      </Badge>
                      {img.is_cover && <Badge variant="default">封面</Badge>}
                    </div>
                    {img.error_msg && (
                      <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", margin: "0 0 var(--space-2) 0" }}>
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

      {/* Right sidebar */}
      <div
        style={{
          position: "sticky",
          top: "calc(var(--nav-height) + var(--space-6))",
          display: "flex",
          flexDirection: "column",
          gap: "var(--space-4)",
        }}
      >
        {/* Publish action */}
        <Card padding="md">
          <EyebrowLabel style={{ margin: "0 0 var(--space-3) 0" }}>
            推送
          </EyebrowLabel>
          <Button
            onClick={() => publish.mutate()}
            disabled={isPublished}
            loading={publish.isPending}
            variant={isPublished ? "secondary" : "success"}
            style={{ width: "100%" }}
          >
            {isPublished
              ? "已推送至微信"
              : publish.isPending
              ? "推送中…"
              : "推送到微信草稿箱"}
          </Button>
          {isPublished && (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)", marginTop: "var(--space-2)", textAlign: "center" }}>
              草稿已发送至微信公众号后台
            </p>
          )}
        </Card>

        {/* Review report */}
        {report.data && (
          <Card padding="md">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "var(--space-4)" }}>
              <EyebrowLabel>审核报告</EyebrowLabel>
              {report.data.overall_score !== null && (
                <div style={{ display: "flex", alignItems: "baseline", gap: "var(--space-1)" }}>
                  <ScoreNumber score={report.data.overall_score} size="lg" />
                  <span style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)", fontVariantNumeric: "tabular-nums" }}>/ 100</span>
                </div>
              )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
              {DIMS.map((d) => {
                const block = report.data![d.key] as DimBlock | null;
                return (
                  <div key={d.key}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: "var(--space-1)",
                      }}
                    >
                      <span style={{ fontSize: "var(--text-sm)", color: "var(--color-ink-2)" }}>{d.label}</span>
                      <ScoreNumber score={block?.score} size="md" />
                    </div>
                    {block?.score !== undefined && (
                      <div
                        style={{
                          height: "3px",
                          backgroundColor: "var(--color-surface-3)",
                          borderRadius: "var(--radius-full)",
                          overflow: "hidden",
                        }}
                      >
                        <div
                          style={{
                            height: "100%",
                            width: `${block.score}%`,
                            backgroundColor:
                              block.score >= 80
                                ? "var(--color-done-fg)"
                                : block.score >= 60
                                ? "var(--color-warn-fg)"
                                : "var(--color-failed-fg)",
                            borderRadius: "var(--radius-full)",
                            transition: "width 0.6s var(--ease-out)",
                          }}
                        />
                      </div>
                    )}
                    {block?.issues && block.issues.length > 0 && (
                      <ul
                        style={{
                          margin: "var(--space-1) 0 0 0",
                          padding: "0 0 0 var(--space-4)",
                          listStyle: "disc",
                        }}
                      >
                        {block.issues.map((it, i) => (
                          <li
                            key={i}
                            style={{
                              fontSize: "var(--text-xs)",
                              color: "var(--color-ink-3)",
                              lineHeight: "var(--leading-snug)",
                            }}
                          >
                            {it}
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Status badge */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "var(--space-3) var(--space-4)",
            backgroundColor: "var(--color-surface-2)",
            borderRadius: "var(--radius-md)",
            border: "1px solid var(--color-surface-3)",
          }}
        >
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>当前状态</span>
          <Badge
            variant={
              detail.data.status === "done" || detail.data.status === "published_to_wechat"
                ? "done"
                : detail.data.status === "failed"
                ? "failed"
                : "processing"
            }
          >
            {detail.data.status}
          </Badge>
        </div>
      </div>
    </div>
  );
}
