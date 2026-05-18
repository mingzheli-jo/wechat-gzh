import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { imagePostsApi, type ImagePost } from "../api/image-posts";
import { Badge, Button, EmptyState, PageSpinner } from "../components/ui";
import { ImagePostFormModal } from "../components/image-posts/ImagePostFormModal";

const STATUS_LABEL: Record<string, string> = {
  pending: "排队中",
  generating: "生成中",
  generated: "可推送",
  composing: "合成中",
  pushing: "推送中",
  pushed: "已推送",
  failed: "失败",
};

const TEMPLATE_LABEL: Record<string, string> = {
  two_panel_contrast: "双格",
  single_panel_caption: "单格",
};

export default function ImagePosts() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["image-posts"],
    queryFn: () => imagePostsApi.list({ page: 1 }),
    refetchInterval: 5000,
  });

  const del = useMutation({
    mutationFn: imagePostsApi.delete,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["image-posts"] }),
  });

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">AI 场景图</h1>
          <p className="text-page-subtitle">主题 → AI 生成 → 推送公众号草稿</p>
        </div>
        <Button onClick={() => setModalOpen(true)}>+ 新建</Button>
      </div>

      {isLoading ? (
        <PageSpinner />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="还没有图片草稿"
          description="点「+ 新建」开始"
          action={<Button onClick={() => setModalOpen(true)}>新建</Button>}
        />
      ) : (
        <div style={{ display: "flex", flexDirection: "column" }}>
          {data.items.map((post: ImagePost) => (
            <div
              key={post.id}
              role="button"
              tabIndex={0}
              onClick={() => navigate(`/image-posts/${post.id}`)}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") navigate(`/image-posts/${post.id}`);
              }}
              style={{
                display: "grid",
                gridTemplateColumns: "60px 1fr 80px 90px 56px",
                gap: "var(--space-4)",
                alignItems: "center",
                padding: "var(--space-4) var(--space-2)",
                borderBottom: "1px solid var(--color-surface-3)",
                cursor: "pointer",
              }}
            >
              <Badge variant="outline">{TEMPLATE_LABEL[post.template]}</Badge>
              <div style={{ minWidth: 0 }}>
                <p style={{ margin: 0, fontSize: "var(--text-base)" }}>
                  {(post.topic || "").slice(0, 30)}
                </p>
                {post.error_msg && (
                  <p style={{ margin: 0, fontSize: "var(--text-xs)", color: "var(--color-failed-fg)" }}>
                    {post.error_msg}
                  </p>
                )}
              </div>
              <span className="mono" style={{ fontSize: "var(--text-xs)" }}>
                {new Date(post.created_at).toLocaleDateString()}
              </span>
              <div style={{ display: "flex", justifyContent: "flex-end" }}>
                <Badge>
                  {STATUS_LABEL[post.status] ?? post.status}
                </Badge>
              </div>
              <div onClick={(e) => e.stopPropagation()} style={{ display: "flex", justifyContent: "flex-end" }}>
                <Button variant="ghost" size="sm" onClick={() => del.mutate(post.id)}>
                  删除
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && (
        <ImagePostFormModal
          open={modalOpen}
          onClose={() => setModalOpen(false)}
          onCreated={(id) => navigate(`/image-posts/${id}`)}
        />
      )}
    </div>
  );
}
