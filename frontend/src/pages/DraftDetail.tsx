import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api/client";

type Detail = {
  id: string;
  title: string | null;
  content_html: string | null;
  status: string;
  review_report_id: string | null;
};

type DimBlock = {
  score?: number;
  issues?: string[];
  similarity?: number;
};

type Report = {
  compliance: DimBlock | null;
  originality: DimBlock | null;
  quality: DimBlock | null;
  clickbait: DimBlock | null;
  overall_score: number | null;
};

const DIMS: { key: keyof Report; label: string }[] = [
  { key: "compliance", label: "合规" },
  { key: "originality", label: "原创度" },
  { key: "quality", label: "质量" },
  { key: "clickbait", label: "标题党" },
];

export default function DraftDetail() {
  const { id } = useParams<{ id: string }>();
  const qc = useQueryClient();

  const detail = useQuery({
    queryKey: ["draft", id],
    queryFn: async () => (await api.get<Detail>(`/drafts/${id}`)).data,
  });

  const report = useQuery({
    queryKey: ["draft-report", id],
    queryFn: async () => (await api.get<Report>(`/drafts/${id}/report`)).data,
    enabled: Boolean(detail.data?.review_report_id),
  });

  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  useEffect(() => {
    if (detail.data) {
      setTitle(detail.data.title ?? "");
      setBody(detail.data.content_html ?? "");
    }
  }, [detail.data]);

  const save = useMutation({
    mutationFn: async () =>
      api.patch(`/drafts/${id}`, { title, content_html: body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
  });

  if (!detail.data) return <div className="p-8">加载中...</div>;

  return (
    <div className="p-8 max-w-4xl space-y-6">
      <input
        className="w-full text-2xl font-semibold border-b py-2"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        placeholder="标题"
      />
      <textarea
        className="w-full h-96 border rounded p-3 font-mono text-sm"
        value={body}
        onChange={(e) => setBody(e.target.value)}
      />
      <button
        onClick={() => save.mutate()}
        disabled={save.isPending}
        className="bg-slate-900 text-white px-4 py-2 rounded"
      >
        {save.isPending ? "保存中..." : "保存"}
      </button>
      <div>
        <h2 className="font-medium mb-2">预览</h2>
        <div
          className="border rounded p-4 prose"
          dangerouslySetInnerHTML={{ __html: body }}
        />
      </div>
      {report.data && (
        <div>
          <h2 className="font-medium mb-2">
            审核报告（综合 {report.data.overall_score}）
          </h2>
          <div className="grid grid-cols-4 gap-3">
            {DIMS.map((d) => {
              const block = report.data[d.key] as DimBlock | null;
              return (
                <div key={d.key} className="border rounded p-3">
                  <div className="text-sm text-slate-500">{d.label}</div>
                  <div className="text-2xl font-semibold">
                    {block?.score ?? "-"}
                  </div>
                  {block?.issues?.length ? (
                    <ul className="text-xs mt-2 list-disc list-inside text-slate-700">
                      {block.issues.map((it, i) => (
                        <li key={i}>{it}</li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
