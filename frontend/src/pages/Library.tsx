import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { api } from "../api/client";

type LibraryStatus = "pending" | "processing" | "done" | "failed";

type LibraryItem = {
  id: string;
  source_url: string;
  original_title: string | null;
  status: LibraryStatus;
  tags: string[] | null;
  error_msg: string | null;
};

type AccountMin = { id: string; name: string };

const STATUS_COLOR: Record<LibraryStatus, string> = {
  pending: "bg-slate-200",
  processing: "bg-blue-200",
  done: "bg-green-200",
  failed: "bg-red-200",
};

export default function Library() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [accountId, setAccountId] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: async () => (await api.get<LibraryItem[]>("/library")).data,
    refetchInterval: 5000,
  });

  const accounts = useQuery({
    queryKey: ["accounts-min"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const ingest = useMutation({
    mutationFn: async () => {
      const urls = text
        .split("\n")
        .map((u) => u.trim())
        .filter(Boolean);
      return api.post("/library", {
        urls,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      });
    },
    onSuccess: () => {
      setText("");
      qc.invalidateQueries({ queryKey: ["library"] });
    },
  });

  const retry = useMutation({
    mutationFn: async (id: string) => api.post(`/library/${id}/retry`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["library"] }),
  });

  const triggerRewrite = useMutation({
    mutationFn: async () =>
      api.post("/drafts/rewrite", {
        library_item_ids: Array.from(selected),
        account_id: accountId,
      }),
    onSuccess: () => {
      setSelected(new Set());
      navigate("/drafts");
    },
  });

  function toggle(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  }

  return (
    <div className="p-8 space-y-6 pb-32">
      <h1 className="text-2xl font-semibold">素材库</h1>

      <div className="space-y-3 border rounded p-4">
        <h2 className="font-medium">添加文章 URL（一行一个）</h2>
        <textarea
          className="w-full border rounded p-2 h-32 font-mono text-sm"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="https://mp.weixin.qq.com/s/..."
        />
        <input
          className="w-full border rounded p-2"
          placeholder="标签（逗号分隔，如 职场,母婴）"
          value={tags}
          onChange={(e) => setTags(e.target.value)}
        />
        <button
          onClick={() => ingest.mutate()}
          disabled={ingest.isPending || !text.trim()}
          className="bg-slate-900 text-white px-4 py-2 rounded disabled:opacity-50"
        >
          {ingest.isPending ? "提交中..." : "添加抓取"}
        </button>
      </div>

      <div>
        <h2 className="font-medium mb-2">列表</h2>
        {isLoading && <div>加载中...</div>}
        <ul className="space-y-2">
          {data?.map((item) => (
            <li key={item.id} className="border rounded p-3">
              <div className="flex justify-between items-start gap-4">
                <input
                  type="checkbox"
                  className="mt-1"
                  disabled={item.status !== "done"}
                  checked={selected.has(item.id)}
                  onChange={() => toggle(item.id)}
                />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">
                    {item.original_title || item.source_url}
                  </div>
                  <div className="text-xs text-slate-500 truncate">
                    {item.source_url}
                  </div>
                  {item.tags?.length ? (
                    <div className="text-xs text-slate-600 mt-1">
                      {item.tags.map((t) => (
                        <span
                          key={t}
                          className="inline-block bg-slate-100 px-2 py-0.5 rounded mr-1"
                        >
                          {t}
                        </span>
                      ))}
                    </div>
                  ) : null}
                  {item.error_msg && (
                    <div className="text-xs text-red-600 mt-1">
                      {item.error_msg}
                    </div>
                  )}
                </div>
                <div className="flex flex-col items-end gap-2">
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${STATUS_COLOR[item.status]}`}
                  >
                    {item.status}
                  </span>
                  {item.status === "failed" && (
                    <button
                      onClick={() => retry.mutate(item.id)}
                      className="text-xs underline"
                    >
                      重试
                    </button>
                  )}
                </div>
              </div>
            </li>
          ))}
        </ul>
      </div>

      {selected.size > 0 && (
        <div className="fixed bottom-0 left-0 right-0 bg-white border-t shadow-lg p-4 flex items-center gap-3">
          <span>当前选中 {selected.size} 篇</span>
          <select
            className="border rounded px-2 py-1"
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
          >
            <option value="">— 选公众号 —</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => triggerRewrite.mutate()}
            disabled={!accountId || triggerRewrite.isPending}
            className="ml-auto bg-slate-900 text-white px-4 py-2 rounded disabled:opacity-50"
          >
            {triggerRewrite.isPending ? "派发中..." : "开始改写"}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-sm text-slate-500"
          >
            清空选择
          </button>
        </div>
      )}
    </div>
  );
}
