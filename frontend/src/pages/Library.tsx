import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

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

const STATUS_COLOR: Record<LibraryStatus, string> = {
  pending: "bg-slate-200",
  processing: "bg-blue-200",
  done: "bg-green-200",
  failed: "bg-red-200",
};

export default function Library() {
  const qc = useQueryClient();
  const [text, setText] = useState("");
  const [tags, setTags] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: async () => (await api.get<LibraryItem[]>("/library")).data,
    refetchInterval: 5000,
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

  return (
    <div className="p-8 space-y-6">
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
    </div>
  );
}
