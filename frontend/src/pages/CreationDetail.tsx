import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import DOMPurify from "dompurify";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { creationsApi, type CreationStatus } from "../api/creations";
import {
  Badge,
  Button,
  EyebrowLabel,
  HairlineMeter,
  HairlineRule,
  PageSpinner,
  ScoreNumber,
} from "../components/ui";

const SANITIZE_CONFIG = {
  ALLOWED_TAGS: ["p", "strong", "em", "br", "h1", "h2", "h3", "img", "a", "ul", "ol", "li", "blockquote"],
  ALLOWED_ATTR: ["src", "alt", "href", "title"],
};

const STATUS_LABEL: Record<CreationStatus, string> = {
  pending: "排队中",
  extracting: "提炼主题",
  retrieving: "检索素材",
  generating: "生成中",
  reviewing: "核查中",
  done: "完成",
  failed: "失败",
};

const RUNNING: CreationStatus[] = [
  "pending",
  "extracting",
  "retrieving",
  "generating",
  "reviewing",
];

function statusVariant(s: CreationStatus): "done" | "failed" | "processing" {
  if (s === "done") return "done";
  if (s === "failed") return "failed";
  return "processing";
}

export default function CreationDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const syncedId = useRef<string | undefined>(undefined);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [tab, setTab] = useState<"edit" | "preview">("preview");
  const [saved, setSaved] = useState(false);

  const detail = useQuery({
    queryKey: ["creation", id],
    queryFn: () => creationsApi.get(id as string),
    enabled: Boolean(id),
    refetchInterval: (query) =>
      query.state.data && RUNNING.includes(query.state.data.status) ? 3000 : false,
  });

  useEffect(() => {
    const d = detail.data;
    if (d && d.id !== syncedId.current) {
      syncedId.current = d.id;
      setTitle(d.generated_title ?? "");
      setBody(d.generated_content_html ?? "");
    }
  }, [detail.data]);

  const save = useMutation({
    mutationFn: () =>
      creationsApi.update(id as string, {
        generated_title: title,
        generated_content_html: body,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["creation", id] });
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    },
  });

  const regenerate = useMutation({
    mutationFn: () => creationsApi.regenerate(id as string),
    onSuccess: () => {
      syncedId.current = undefined;
      qc.invalidateQueries({ queryKey: ["creation", id] });
    },
  });

  const safeBody = useMemo(() => DOMPurify.sanitize(body, SANITIZE_CONFIG), [body]);

  if (!detail.data) return <PageSpinner />;
  const d = detail.data;
  const isRunning = RUNNING.includes(d.status);
  const sources = d.retrieved_sources ?? [];
  const fc = d.fact_check;

  return (
    <div className="page-shell page-shell-wide" style={{ paddingBottom: "var(--space-20)" }}>
      {/* Breadcrumb */}
      <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-6)" }}>
        <Link to="/creations" className="mono" style={{ color: "var(--color-ink-3)", textDecoration: "none" }}>
          主题创作
        </Link>
        <span className="mono" style={{ color: "var(--color-ink-4)" }}>/</span>
        <span className="mono" style={{ color: "var(--color-ink-2)" }}>
          {(title || d.source_title || "创作").slice(0, 30)}
        </span>
        <div style={{ flex: 1 }} />
        <Badge variant={statusVariant(d.status)}>{STATUS_LABEL[d.status]}</Badge>
      </div>

      <HairlineRule style={{ marginBottom: "var(--space-8)" }} />

      {/* Theme banner */}
      <section
        className="surface-panel"
        style={{ padding: "var(--space-5)", marginBottom: "var(--space-6)" }}
      >
        <EyebrowLabel>提炼主题（约 100 字）</EyebrowLabel>
        <p style={{ margin: "var(--space-2) 0 0 0", lineHeight: "var(--leading-loose)", color: "var(--color-ink)" }}>
          {d.extracted_theme ?? (isRunning ? "提炼中…" : "—")}
        </p>
        {d.keywords && d.keywords.length > 0 && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-1)", marginTop: "var(--space-3)" }}>
            {d.keywords.map((k) => (
              <Badge key={k} variant="outline">{k}</Badge>
            ))}
          </div>
        )}
        {d.source_url && (
          <a
            href={d.source_url}
            target="_blank"
            rel="noopener noreferrer"
            style={{ display: "inline-block", marginTop: "var(--space-3)", fontSize: "var(--text-xs)", color: "var(--color-link)" }}
          >
            原文链接 ↗
          </a>
        )}
      </section>

      {d.error_msg && (
        <div role="alert" style={{ marginBottom: "var(--space-6)", padding: "var(--space-3) var(--space-4)", background: "var(--color-failed)", color: "var(--color-failed-fg)", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)" }}>
          {d.error_msg}
        </div>
      )}

      {/* Two columns: article | sidebar */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 340px", gap: "var(--space-6)", alignItems: "start" }}>
        {/* LEFT — generated article */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={isRunning ? "生成中…" : "文章标题"}
            className="text-editorial-title"
            style={{
              width: "100%",
              background: "none",
              border: "none",
              borderBottom: "1px dashed var(--color-surface-3)",
              outline: "none",
              padding: "var(--space-2) 0",
              boxSizing: "border-box",
            }}
          />

          <div>
            <div style={{ display: "flex", alignItems: "center", borderBottom: "1px solid var(--color-surface-3)", marginBottom: "var(--space-4)" }}>
              {(["preview", "edit"] as const).map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  style={{
                    padding: "var(--space-2) var(--space-4)",
                    fontSize: "var(--text-sm)",
                    fontWeight: tab === t ? "var(--weight-medium)" : "var(--weight-normal)",
                    color: tab === t ? "var(--color-ink)" : "var(--color-ink-3)",
                    background: "none",
                    border: "none",
                    borderBottom: tab === t ? "2px solid var(--color-ink)" : "2px solid transparent",
                    cursor: "pointer",
                    marginBottom: "-1px",
                  }}
                >
                  {t === "preview" ? "预览" : "编辑 HTML"}
                </button>
              ))}
            </div>

            {tab === "preview" ? (
              <div
                className="prose-preview"
                style={{
                  minHeight: "50vh",
                  padding: "var(--space-6)",
                  backgroundColor: "var(--color-white)",
                  border: "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                }}
                dangerouslySetInnerHTML={{ __html: safeBody || (isRunning ? "<p>正在生成…</p>" : "<p>（暂无内容）</p>") }}
              />
            ) : (
              <textarea
                value={body}
                onChange={(e) => setBody(e.target.value)}
                className="input-base input-mono"
                style={{
                  minHeight: "50vh",
                  resize: "vertical",
                  lineHeight: "var(--leading-loose)",
                  border: "none",
                  backgroundColor: "var(--color-surface-2)",
                  padding: "var(--space-5)",
                  borderRadius: "var(--radius-md)",
                }}
              />
            )}
          </div>
        </div>

        {/* RIGHT — sidebar: fact check + sources */}
        <div style={{ position: "sticky", top: "var(--space-8)", display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
          {/* Fact-consistency */}
          <div>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
              <EyebrowLabel>事实一致性</EyebrowLabel>
              {fc && fc.note === undefined && <ScoreNumber score={fc.score ?? undefined} size="md" />}
            </div>
            {fc?.note ? (
              <p style={{ margin: "var(--space-2) 0 0 0", fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", lineHeight: "var(--leading-snug)" }}>
                {fc.note}
              </p>
            ) : fc ? (
              <>
                <HairlineMeter score={fc.score ?? undefined} style={{ marginTop: "var(--space-2)" }} />
                {fc.unsupported_claims.length > 0 && (
                  <div style={{ marginTop: "var(--space-3)" }}>
                    <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>
                      疑似无依据（{fc.unsupported_claims.length}）
                    </p>
                    {fc.unsupported_claims.map((c, i) => (
                      <p key={i} style={{ margin: "var(--space-1) 0 0 0", fontSize: "var(--text-xs)", fontStyle: "italic", color: "var(--color-ink-2)", lineHeight: "var(--leading-snug)" }}>
                        — {c}
                      </p>
                    ))}
                  </div>
                )}
                {fc.unsupported_claims.length === 0 && fc.issues.length === 0 && (
                  <p style={{ margin: "var(--space-2) 0 0 0", fontSize: "var(--text-xs)", color: "var(--color-done-fg)" }}>
                    所有事实均有素材支撑
                  </p>
                )}
              </>
            ) : (
              <p style={{ margin: "var(--space-2) 0 0 0", fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>
                {isRunning ? "核查待运行…" : "—"}
              </p>
            )}
          </div>

          <HairlineRule />

          {/* Retrieved sources */}
          <div>
            <EyebrowLabel>引用素材（{sources.length}）</EyebrowLabel>
            {sources.length === 0 ? (
              <p style={{ margin: "var(--space-2) 0 0 0", fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>
                {isRunning ? "检索中…" : "未检索到库内相关素材"}
              </p>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)", marginTop: "var(--space-2)" }}>
                {sources.map((s, i) => (
                  <div key={s.library_item_id} style={{ fontSize: "var(--text-xs)" }}>
                    <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "baseline" }}>
                      <span className="mono" style={{ color: "var(--color-ink-4)" }}>[{i + 1}]</span>
                      <span style={{ color: "var(--color-ink)", fontWeight: "var(--weight-medium)", lineHeight: "var(--leading-snug)" }}>
                        {s.title ?? "（无标题）"}
                      </span>
                    </div>
                    <div style={{ display: "flex", gap: "var(--space-2)", alignItems: "center", marginTop: "var(--space-1)", paddingLeft: "1.4em" }}>
                      <Badge variant="outline">相关度 {s.relevance}</Badge>
                      {s.source_url && (
                        <a href={s.source_url} target="_blank" rel="noopener noreferrer" style={{ color: "var(--color-link)" }}>
                          原文 ↗
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div className="action-bar">
        {saved && (
          <span style={{ fontSize: "var(--text-xs)", color: "var(--color-done-fg)", fontFamily: "var(--font-mono)" }}>
            已保存
          </span>
        )}
        <div style={{ flex: 1 }} />
        <Button
          variant="secondary"
          onClick={() => {
            if (window.confirm("将清空当前生成结果，重新检索并生成。是否继续？")) {
              regenerate.mutate();
            }
          }}
          disabled={isRunning || regenerate.isPending}
          loading={regenerate.isPending}
          style={{ backgroundColor: "rgba(255,255,255,0.12)", color: "var(--color-white)", border: "1px solid rgba(255,255,255,0.2)", flexShrink: 0 }}
        >
          {regenerate.isPending ? "重新生成中…" : "重新生成"}
        </Button>
        <Button
          variant="primary"
          onClick={() => save.mutate()}
          loading={save.isPending}
          disabled={isRunning}
          style={{ flexShrink: 0 }}
        >
          {save.isPending ? "保存中…" : "保存"}
        </Button>
      </div>
    </div>
  );
}
