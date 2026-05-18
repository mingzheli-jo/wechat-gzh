import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import { imageAssetsApi, type ImageAsset } from "../api/image-posts";
import { Badge, EmptyState, EyebrowLabel, PageSpinner } from "../components/ui";

interface AccountMin {
  id: string;
  name: string;
}

export default function ImageAssets() {
  const [accountId, setAccountId] = useState<string>("");

  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const assets = useQuery({
    queryKey: ["image-assets-browse", accountId],
    queryFn: () => imageAssetsApi.list({ account_id: accountId }),
    enabled: Boolean(accountId),
  });

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">图库</h1>
          <p className="text-page-subtitle">已生成的角色场景图，可在创建新草稿时复用</p>
        </div>
      </div>

      <div style={{ marginBottom: "var(--space-4)" }}>
        <EyebrowLabel>选择公众号</EyebrowLabel>
        <select
          value={accountId}
          onChange={(e) => setAccountId(e.target.value)}
          style={{ marginTop: "var(--space-2)", padding: "var(--space-2)", minWidth: 200 }}
        >
          <option value="">— 选 —</option>
          {accounts.data?.map((a) => (
            <option key={a.id} value={a.id}>{a.name}</option>
          ))}
        </select>
      </div>

      {!accountId ? (
        <EmptyState title="请先选公众号" description="不同公众号有独立的图库" />
      ) : assets.isLoading ? (
        <PageSpinner />
      ) : !assets.data || assets.data.items.length === 0 ? (
        <EmptyState title="还没有图" description="先在「AI 场景图」生成几张" />
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
          {assets.data.items.map((a: ImageAsset) => (
            <div key={a.id} style={{
              border: "1px solid var(--color-surface-3)",
              borderRadius: "var(--radius-md)", overflow: "hidden",
            }}>
              <img
                src={imageAssetsApi.fileUrl(a.id)}
                alt={a.scene_prompt ?? ""}
                style={{ width: "100%", aspectRatio: "1/1", objectFit: "cover", display: "block" }}
              />
              <div style={{ padding: "var(--space-3)", fontSize: "var(--text-xs)" }}>
                <p style={{ margin: 0, color: "var(--color-ink-2)" }}>
                  {(a.scene_prompt ?? "").slice(0, 60)}
                </p>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: "var(--space-2)" }}>
                  <Badge variant="outline">复用 {a.used_count} 次</Badge>
                  <span className="mono" style={{ color: "var(--color-ink-3)" }}>
                    {new Date(a.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
