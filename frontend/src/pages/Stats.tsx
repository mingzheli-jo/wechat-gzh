import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  statsApi,
  type AccountStatsRow,
} from "../api/stats";
import { Button, EmptyState, PageSpinner } from "../components/ui";

type SortKey = keyof Pick<
  AccountStatsRow,
  | "name"
  | "follower_count"
  | "new_follow_yesterday"
  | "cancel_follow_yesterday"
  | "articles_count_30d"
  | "total_read_30d"
>;

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

export default function Stats() {
  const qc = useQueryClient();
  const [sortKey, setSortKey] = useState<SortKey>("total_read_30d");
  const [order, setOrder] = useState<"asc" | "desc">("desc");

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["stats", "accounts"],
    queryFn: () => statsApi.listAccounts(),
  });

  const refreshAll = useMutation({
    mutationFn: () => statsApi.refresh(),
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      }, 3000);
    },
  });

  const refreshOne = useMutation({
    mutationFn: (id: string) => statsApi.refresh(id),
    onSuccess: () => {
      setTimeout(() => {
        qc.invalidateQueries({ queryKey: ["stats", "accounts"] });
      }, 3000);
    },
  });

  const rows = (data ?? []).slice().sort((a, b) => {
    const av = a[sortKey];
    const bv = b[sortKey];
    if (typeof av === "string" && typeof bv === "string") {
      return order === "desc" ? bv.localeCompare(av) : av.localeCompare(bv);
    }
    return order === "desc" ? Number(bv) - Number(av) : Number(av) - Number(bv);
  });

  const toggleSort = (k: SortKey) => {
    if (sortKey === k) {
      setOrder(order === "desc" ? "asc" : "desc");
    } else {
      setSortKey(k);
      setOrder("desc");
    }
  };

  if (isLoading) {
    return (
      <div className="page-shell">
        <div className="page-header">
          <div className="page-header-meta">
            <h1 className="text-page-title">数据</h1>
          </div>
        </div>
        <PageSpinner />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="page-shell">
        <div className="page-header">
          <div className="page-header-meta">
            <h1 className="text-page-title">数据</h1>
          </div>
        </div>
        <div>加载失败：{String(error)}</div>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="page-shell">
        <div className="page-header">
          <div className="page-header-meta">
            <h1 className="text-page-title">数据</h1>
          </div>
        </div>
        <EmptyState
          title="还没有同步过统计数据"
          description="点「立即同步」开始抓取每个公众号的粉丝和文章数据。"
          action={
            <Button
              onClick={() => refreshAll.mutate()}
              loading={refreshAll.isPending}
            >
              立即同步
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="page-shell">
      <div className="page-header">
        <div className="page-header-meta">
          <h1 className="text-page-title">数据</h1>
          <p className="text-page-subtitle">公众号粉丝 + 文章阅读统计</p>
        </div>
        <Button
          onClick={() => refreshAll.mutate()}
          loading={refreshAll.isPending}
          disabled={refreshAll.isPending}
        >
          全局刷新
        </Button>
      </div>

      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid currentColor" }}>
            <Th label="账号" sortKey="name" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="当前粉丝" sortKey="follower_count" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="昨日新增" sortKey="new_follow_yesterday" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="昨日取消" sortKey="cancel_follow_yesterday" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="30 天文章数" sortKey="articles_count_30d" current={sortKey} order={order} onClick={toggleSort} />
            <Th label="30 天总阅读" sortKey="total_read_30d" current={sortKey} order={order} onClick={toggleSort} />
            <th style={{ textAlign: "left", padding: "12px 8px" }}>同步时间</th>
            <th style={{ textAlign: "left", padding: "12px 8px" }}>操作</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr
              key={r.account_id}
              style={{ borderBottom: "1px solid rgba(0,0,0,0.1)" }}
            >
              <td style={{ padding: "12px 8px" }}>{r.name}</td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>
                {r.follower_count.toLocaleString()}
              </td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>
                +{r.new_follow_yesterday}
              </td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>
                -{r.cancel_follow_yesterday}
              </td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>
                {r.articles_count_30d}
              </td>
              <td style={{ padding: "12px 8px", fontVariantNumeric: "tabular-nums" }}>
                {r.total_read_30d.toLocaleString()}
              </td>
              <td style={{ padding: "12px 8px" }}>{formatRelative(r.stats_synced_at)}</td>
              <td style={{ padding: "12px 8px" }}>
                <Link to={`/stats/${r.account_id}`}>查看明细</Link>
                {" · "}
                <button
                  type="button"
                  onClick={() => refreshOne.mutate(r.account_id)}
                  disabled={
                    refreshOne.isPending && refreshOne.variables === r.account_id
                  }
                >
                  刷新本号
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

interface ThProps {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  order: "asc" | "desc";
  onClick: (k: SortKey) => void;
}

function Th({ label, sortKey, current, order, onClick }: ThProps) {
  const active = sortKey === current;
  return (
    <th
      style={{
        textAlign: "left",
        padding: "12px 8px",
        cursor: "pointer",
        userSelect: "none",
      }}
      onClick={() => onClick(sortKey)}
    >
      {label} {active ? (order === "desc" ? "▼" : "▲") : ""}
    </th>
  );
}
