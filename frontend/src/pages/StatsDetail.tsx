import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { statsApi } from "../api/stats";
import { Button, PageSpinner } from "../components/ui";

type SortField =
  | "publish_time"
  | "read_count"
  | "like_count"
  | "share_count"
  | "comment_count";

function formatRelative(iso: string | null): string {
  if (!iso) return "从未同步";
  const diffMs = Date.now() - new Date(iso).getTime();
  const diffMin = Math.floor(diffMs / 60_000);
  if (diffMin < 1) return "刚刚";
  if (diffMin < 60) return `${diffMin} 分钟前`;
  const diffH = Math.floor(diffMin / 60);
  if (diffH < 24) return `${diffH} 小时前`;
  const diffD = Math.floor(diffH / 24);
  return `${diffD} 天前`;
}

export default function StatsDetail() {
  const { accountId } = useParams<{ accountId: string }>();
  const qc = useQueryClient();
  const [days, setDays] = useState<7 | 30 | 90>(30);
  const [sort, setSort] = useState<SortField>("publish_time");

  const accounts = useQuery({
    queryKey: ["stats", "accounts"],
    queryFn: () => statsApi.listAccounts(),
  });
  const account = accounts.data?.find((a) => a.account_id === accountId);

  const articles = useQuery({
    queryKey: ["stats", "articles", accountId, days, sort],
    queryFn: () =>
      statsApi.listArticles(accountId!, { days, sort, order: "desc" }),
    enabled: !!accountId,
  });

  const [pollUntil, setPollUntil] = useState<number | null>(null);

  const refresh = useMutation({
    mutationFn: () => statsApi.refresh(accountId!),
    onSuccess: () => {
      setPollUntil(Date.now() + 30_000);
    },
  });

  useEffect(() => {
    if (pollUntil === null) return;
    if (Date.now() > pollUntil) {
      setPollUntil(null);
      return;
    }
    const id = setTimeout(() => {
      qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      qc.invalidateQueries({ queryKey: ["stats", "articles", accountId] });
      setPollUntil((p) => (p && Date.now() < p ? p : null));
    }, 3000);
    return () => clearTimeout(id);
  }, [pollUntil, qc, accountId, accounts.dataUpdatedAt]);

  if (!accountId) return <div className="page-shell">缺少 accountId</div>;
  if (accounts.isLoading) return <div className="page-shell"><PageSpinner /></div>;
  if (!account) return <div className="page-shell">账号不存在</div>;

  return (
    <div className="page-shell">
      <div style={{ marginBottom: 16 }}>
        <Link to="/stats">← 返回</Link>
      </div>
      <div
        className="page-header"
        style={{
          marginBottom: 24,
          paddingBottom: 16,
          borderBottom: "1px solid currentColor",
        }}
      >
        <div className="page-header-meta">
          <h1 className="text-page-title">{account.name}</h1>
          <p className="text-page-subtitle" style={{ fontVariantNumeric: "tabular-nums" }}>
            当前粉丝 {account.follower_count.toLocaleString()} · 昨日 +
            {account.new_follow_yesterday} / -{account.cancel_follow_yesterday}{" "}
            · 同步于 {formatRelative(account.stats_synced_at)}
          </p>
        </div>
        <Button
          onClick={() => refresh.mutate()}
          disabled={refresh.isPending || pollUntil !== null}
          loading={refresh.isPending || pollUntil !== null}
        >
          {pollUntil !== null ? "刷新中…" : "刷新本号"}
        </Button>
      </div>

      <div style={{ display: "flex", gap: 16, marginBottom: 16 }}>
        <div>
          时间范围：
          {([7, 30, 90] as const).map((d) => (
            <button
              key={d}
              type="button"
              onClick={() => setDays(d)}
              style={{
                marginLeft: 8,
                fontWeight: d === days ? "bold" : "normal",
              }}
            >
              {d} 天
            </button>
          ))}
        </div>
        <div>
          排序：
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value as SortField)}
          >
            <option value="publish_time">发布时间</option>
            <option value="read_count">阅读</option>
            <option value="like_count">点赞</option>
            <option value="share_count">分享</option>
            <option value="comment_count">评论</option>
          </select>
        </div>
      </div>

      {articles.isLoading ? (
        <PageSpinner />
      ) : articles.data && articles.data.length > 0 ? (
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ borderBottom: "2px solid currentColor" }}>
              <th style={{ textAlign: "left", padding: "12px 8px" }}>标题</th>
              <th style={{ textAlign: "left", padding: "12px 8px" }}>发布时间</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>阅读</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>点赞</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>分享</th>
              <th style={{ textAlign: "right", padding: "12px 8px" }}>评论</th>
            </tr>
          </thead>
          <tbody>
            {articles.data.map((a) => (
              <tr
                key={`${a.msgid}_${a.article_idx}`}
                style={{ borderBottom: "1px solid rgba(0,0,0,0.1)" }}
              >
                <td style={{ padding: "12px 8px" }}>{a.title}</td>
                <td style={{ padding: "12px 8px" }}>
                  {new Date(a.publish_time).toLocaleDateString()}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.read_count.toLocaleString()}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.like_count}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.share_count}
                </td>
                <td style={{ padding: "12px 8px", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
                  {a.comment_count}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>该账号在最近 {days} 天内没有发表文章。</p>
      )}
    </div>
  );
}
