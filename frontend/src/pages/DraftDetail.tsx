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

type Img = {
  id: string;
  original_url: string;
  wechat_url: string | null;
  status: string;
  is_cover: boolean;
  error_msg: string | null;
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

  const images = useQuery({
    queryKey: ["draft-images", id],
    queryFn: async () =>
      (await api.get<Img[]>(`/images/by-draft/${id}`)).data,
    refetchInterval: 5000,
  });

  const setCover = useMutation({
    mutationFn: async (imgId: string) => api.post(`/images/${imgId}/cover`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
  });

  const removeImg = useMutation({
    mutationFn: async (imgId: string) => api.delete(`/images/${imgId}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft-images", id] }),
  });

  const publish = useMutation({
    mutationFn: async () => api.post(`/drafts/${id}/publish-to-wechat`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["draft", id] }),
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

      {images.data && images.data.length > 0 && (
        <div>
          <h2 className="font-medium mb-2">图片复核</h2>
          <div className="grid grid-cols-3 md:grid-cols-4 gap-3">
            {images.data.map((img) => (
              <div
                key={img.id}
                className={`border rounded p-2 ${
                  img.is_cover ? "ring-2 ring-blue-500" : ""
                }`}
              >
                <img
                  src={img.wechat_url ?? img.original_url}
                  className="w-full h-32 object-cover rounded"
                />
                <div className="text-xs mt-1 text-slate-600">
                  {img.status}
                  {img.is_cover ? " · 封面" : ""}
                </div>
                {img.error_msg && (
                  <div className="text-xs text-red-600">{img.error_msg}</div>
                )}
                <div className="flex gap-2 mt-2 text-xs">
                  <button
                    onClick={() => setCover.mutate(img.id)}
                    disabled={img.is_cover}
                    className="underline disabled:opacity-50"
                  >
                    设为封面
                  </button>
                  <button
                    onClick={() => removeImg.mutate(img.id)}
                    className="underline text-red-600"
                  >
                    删除
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <button
        onClick={() => publish.mutate()}
        disabled={
          detail.data?.status === "published_to_wechat" || publish.isPending
        }
        className="bg-emerald-700 text-white px-4 py-2 rounded disabled:opacity-50"
      >
        {detail.data?.status === "published_to_wechat"
          ? "已推送到微信"
          : publish.isPending
            ? "推送中..."
            : "推送到微信草稿箱"}
      </button>
    </div>
  );
}
