import { api } from "./client";

export interface AccountStatsRow {
  account_id: string;
  name: string;
  follower_count: number;
  new_follow_yesterday: number;
  cancel_follow_yesterday: number;
  articles_count_30d: number;
  total_read_30d: number;
  stats_synced_at: string | null;
}

export interface ArticleStatsRow {
  msgid: number;
  article_idx: number;
  title: string;
  publish_time: string;
  read_count: number;
  like_count: number;
  share_count: number;
  comment_count: number;
  last_synced_at: string;
}

export interface RefreshTriggerResponse {
  job_id: string;
  status: "queued";
}

export const statsApi = {
  listAccounts() {
    return api.get<AccountStatsRow[]>("/stats/accounts").then((r) => r.data);
  },
  listArticles(
    accountId: string,
    params: { days?: number; sort?: string; order?: "asc" | "desc" } = {},
  ) {
    return api
      .get<ArticleStatsRow[]>(`/stats/accounts/${accountId}/articles`, {
        params,
      })
      .then((r) => r.data);
  },
  refresh(accountId?: string) {
    const params = accountId ? { account_id: accountId } : undefined;
    return api
      .post<RefreshTriggerResponse>("/stats/refresh", null, { params })
      .then((r) => r.data);
  },
};
