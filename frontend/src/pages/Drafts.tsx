import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { api } from "../api/client";

type Draft = {
  id: string;
  title: string | null;
  status: string;
  error_msg: string | null;
  review_report_id: string | null;
  created_at: string;
};

export default function Drafts() {
  const { data, isLoading } = useQuery({
    queryKey: ["drafts"],
    queryFn: async () => (await api.get<Draft[]>("/drafts")).data,
    refetchInterval: 5000,
  });
  return (
    <div className="p-8">
      <h1 className="text-2xl font-semibold mb-4">草稿</h1>
      {isLoading && <div>加载中...</div>}
      <ul className="space-y-2">
        {data?.map((d) => (
          <li key={d.id} className="border rounded p-3">
            <Link to={`/drafts/${d.id}`} className="block">
              <div className="font-medium">{d.title ?? "(尚未生成)"}</div>
              <div className="text-xs text-slate-500">
                {d.status} · {new Date(d.created_at).toLocaleString()}
              </div>
              {d.error_msg && (
                <div className="text-xs text-red-600 mt-1">{d.error_msg}</div>
              )}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
