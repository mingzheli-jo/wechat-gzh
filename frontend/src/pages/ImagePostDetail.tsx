import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import { imageAssetsApi, imagePostsApi } from "../api/image-posts";
import { CompositionCanvas } from "../components/image-posts/CompositionCanvas";
import { Badge, Button, EyebrowLabel, Input, PageSpinner } from "../components/ui";

interface AccountMin {
  id: string;
  name: string;
}

const TEMPLATE_LABEL: Record<string, string> = {
  two_panel_contrast: "双格反差",
  single_panel_caption: "单格大字",
};

const STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  generating: "生成中",
  generated: "可推送",
  composing: "合成中",
  pushing: "推送中",
  pushed: "已推送",
  failed: "失败",
};

const TERMINAL = new Set(["pushed", "failed", "generated"]);

export default function ImagePostDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();
  const [captions, setCaptions] = useState<string[]>([]);

  const detail = useQuery({
    queryKey: ["image-post", id],
    queryFn: () => imagePostsApi.get(id!),
    refetchInterval: (q) =>
      q.state.data && TERMINAL.has(q.state.data.status) ? false : 2000,
  });

  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  // Only initialise captions from server when local state is empty, to avoid
  // clobbering in-progress edits on background refetches.
  useEffect(() => {
    if (detail.data?.captions && captions.length === 0) {
      setCaptions(detail.data.captions);
    }
  }, [detail.data?.captions]); // eslint-disable-line react-hooks/exhaustive-deps

  const saveCaptions = useMutation({
    mutationFn: () => imagePostsApi.patch(id!, { captions }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  const regenCaptions = useMutation({
    mutationFn: () => imagePostsApi.regenerateCaptions(id!),
    onSuccess: () => {
      // Clear local captions so the next detail refetch re-syncs server state.
      setCaptions([]);
      qc.invalidateQueries({ queryKey: ["image-post", id] });
    },
  });

  const regenerate = useMutation({
    mutationFn: () => imagePostsApi.regenerate(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  const pushToWechat = useMutation({
    mutationFn: () => imagePostsApi.push(id!),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-post", id] }),
  });

  if (!detail.data) return <PageSpinner />;

  const post = detail.data;
  const account = accounts.data?.find((a) => a.id === post.account_id);
  const panelImageUrls = (post.asset_ids ?? []).map((aid) => imageAssetsApi.fileUrl(aid));
  const canPush = post.status === "generated" || post.status === "failed";

  return (
    <div className="page-shell">
      <div style={{ marginBottom: "var(--space-4)" }}>
        <Link to="/image-posts">← 返回列表</Link>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 360px",
          gap: "var(--space-6)",
          alignItems: "start",
        }}
      >
        {/* LEFT — Canvas preview */}
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
          <EyebrowLabel>预览</EyebrowLabel>
          {panelImageUrls.length > 0 && captions.length > 0 ? (
            <CompositionCanvas
              panelImageUrls={panelImageUrls}
              captions={captions}
              template={post.template}
              watermark={`公众号·${account?.name ?? ""}`}
            />
          ) : (
            <div
              style={{
                minHeight: "60vh",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--color-surface-2)",
                borderRadius: "var(--radius-md)",
              }}
            >
              {post.status === "generating" ? "生成中…" : "暂无候选图"}
            </div>
          )}
          <div style={{ display: "flex", gap: "var(--space-2)" }}>
            <Button
              variant="secondary"
              onClick={() => regenerate.mutate()}
              loading={regenerate.isPending}
              disabled={!TERMINAL.has(post.status)}
            >
              重新生成图
            </Button>
          </div>
        </div>

        {/* RIGHT — editor sidebar */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: "var(--space-4)",
            position: "sticky",
            top: 0,
          }}
        >
          <Badge>{STATUS_LABEL[post.status] ?? post.status}</Badge>

          {post.error_msg && (
            <div
              style={{
                padding: "var(--space-3)",
                background: "var(--color-failed)",
                color: "var(--color-failed-fg)",
                borderRadius: "var(--radius-md)",
                fontSize: "var(--text-sm)",
              }}
            >
              {post.error_msg}
            </div>
          )}

          <div>
            <EyebrowLabel>文案</EyebrowLabel>
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-2)",
                marginTop: "var(--space-2)",
              }}
            >
              {captions.map((cap, i) => (
                <Input
                  key={i}
                  value={cap}
                  onChange={(e) => {
                    const next = [...captions];
                    next[i] = e.target.value;
                    setCaptions(next);
                  }}
                  placeholder={`文案 ${i + 1}`}
                />
              ))}
            </div>
            <div
              style={{
                display: "flex",
                gap: "var(--space-2)",
                marginTop: "var(--space-2)",
              }}
            >
              <Button
                variant="secondary"
                size="sm"
                onClick={() => saveCaptions.mutate()}
                loading={saveCaptions.isPending}
              >
                保存文案
              </Button>
              <Button
                variant="secondary"
                size="sm"
                onClick={() => regenCaptions.mutate()}
                loading={regenCaptions.isPending}
              >
                重写文案
              </Button>
            </div>
          </div>

          <div>
            <EyebrowLabel>元信息</EyebrowLabel>
            <div
              style={{
                fontSize: "var(--text-sm)",
                color: "var(--color-ink-2)",
                marginTop: "var(--space-2)",
                lineHeight: 1.7,
              }}
            >
              <p>主题：{post.topic}</p>
              <p>语气：{post.tone ?? "—"}</p>
              <p>模板：{TEMPLATE_LABEL[post.template] ?? post.template}</p>
              <p>公众号：{account?.name ?? "—"}</p>
              <p>创建：{new Date(post.created_at).toLocaleString()}</p>
            </div>
          </div>

          <Button
            variant="primary"
            onClick={() => pushToWechat.mutate()}
            disabled={!canPush || pushToWechat.isPending || captions.length === 0}
            loading={pushToWechat.isPending}
          >
            {post.status === "pushed" ? "已推送" : "推送到微信草稿箱"}
          </Button>
        </div>
      </div>
    </div>
  );
}
