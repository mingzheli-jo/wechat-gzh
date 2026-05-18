import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api/client";
import {
  imagePostsApi,
  type ImagePostTemplate,
} from "../../api/image-posts";
import { Button, Modal, Textarea } from "../ui";
import { AssetPickerModal } from "./AssetPickerModal";

interface AccountMin {
  id: string;
  name: string;
  character_reference_path: string | null;
}

interface Props {
  open: boolean;
  onClose: () => void;
  onCreated: (postId: string) => void;
}

const TONES = [
  { value: "humor", label: "幽默" },
  { value: "self_mockery", label: "自嘲" },
  { value: "poignant", label: "扎心" },
  { value: "warm", label: "温暖" },
];

export function ImagePostFormModal({ open, onClose, onCreated }: Props) {
  const accounts = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<AccountMin[]>("/accounts")).data,
  });

  const [accountId, setAccountId] = useState("");
  const [template, setTemplate] = useState<ImagePostTemplate>("two_panel_contrast");
  const [topic, setTopic] = useState("");
  const [tone, setTone] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [imageSource, setImageSource] = useState<"new" | "reuse">("new");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [pickedAssetIds, setPickedAssetIds] = useState<string[]>([]);

  const create = useMutation({
    mutationFn: async () => {
      const data = await imagePostsApi.create({
        account_id: accountId,
        template,
        topic,
        tone,
        panel_asset_ids: imageSource === "reuse" ? pickedAssetIds : null,
      });
      return data;
    },
    onSuccess: (data) => {
      onCreated(data.id);
      onClose();
    },
    onError: (e: unknown) => {
      const d = (e as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      setError(d ?? "创建失败");
    },
  });

  const account = accounts.data?.find((a) => a.id === accountId);
  const needsCharRef = account && !account.character_reference_path;

  return (
    <>
    <Modal
      open={open}
      onClose={onClose}
      title="新建 AI 场景图"
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={create.isPending}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={() => create.mutate()}
            disabled={
              !accountId ||
              !topic.trim() ||
              create.isPending ||
              !!needsCharRef ||
              (imageSource === "reuse" &&
                pickedAssetIds.length !== (template === "two_panel_contrast" ? 2 : 1))
            }
            loading={create.isPending}
          >
            生成
          </Button>
        </>
      }
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>公众号</label>
          <select
            value={accountId}
            onChange={(e) => setAccountId(e.target.value)}
            style={{ width: "100%", padding: "var(--space-2)", marginTop: "var(--space-1)" }}
          >
            <option value="">— 选择公众号 —</option>
            {accounts.data?.map((a) => (
              <option key={a.id} value={a.id}>{a.name}</option>
            ))}
          </select>
          {needsCharRef && (
            <p style={{ fontSize: "var(--text-xs)", color: "var(--color-failed-fg)", marginTop: "var(--space-1)" }}>
              该公众号未上传角色参考图，请先在「公众号」页配置
            </p>
          )}
        </div>

        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>模板</label>
          <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
            {[
              { v: "two_panel_contrast", l: "双格反差" },
              { v: "single_panel_caption", l: "单格大字" },
            ].map((t) => (
              <button
                key={t.v}
                type="button"
                onClick={() => setTemplate(t.v as ImagePostTemplate)}
                style={{
                  flex: 1,
                  padding: "var(--space-2) var(--space-3)",
                  border: template === t.v ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  background: template === t.v ? "var(--color-surface-2)" : "transparent",
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                }}
              >
                {t.l}
              </button>
            ))}
          </div>
        </div>

        <Textarea
          label="主题"
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="例：打工人对周一开会的态度 vs 周五下午的态度"
          rows={4}
        />

        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>语气（可选）</label>
          <div style={{ display: "flex", gap: "var(--space-1)", marginTop: "var(--space-1)", flexWrap: "wrap" }}>
            {TONES.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTone(tone === t.value ? null : t.value)}
                style={{
                  padding: "var(--space-1) var(--space-3)",
                  border: tone === t.value ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  background: tone === t.value ? "var(--color-surface-2)" : "transparent",
                  borderRadius: "var(--radius-full)",
                  cursor: "pointer",
                  fontSize: "var(--text-xs)",
                }}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-3)" }}>图源</label>
          <div style={{ display: "flex", gap: "var(--space-2)", marginTop: "var(--space-1)" }}>
            {[
              { v: "new", l: "AI 新生成" },
              { v: "reuse", l: "从图库选" },
            ].map((s) => (
              <button
                key={s.v}
                type="button"
                onClick={() => {
                  setImageSource(s.v as "new" | "reuse");
                  if (s.v === "new") setPickedAssetIds([]);
                }}
                style={{
                  flex: 1,
                  padding: "var(--space-2)",
                  border: imageSource === s.v ? "2px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  background: imageSource === s.v ? "var(--color-surface-2)" : "transparent",
                  borderRadius: "var(--radius-md)",
                  cursor: "pointer",
                  fontSize: "var(--text-sm)",
                }}
              >
                {s.l}
              </button>
            ))}
          </div>
          {imageSource === "reuse" && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setPickerOpen(true)}
              style={{ marginTop: "var(--space-2)" }}
              disabled={!accountId}
            >
              {pickedAssetIds.length > 0 ? `已选 ${pickedAssetIds.length} 张` : "选择图片"}
            </Button>
          )}
        </div>

        {error && (
          <p style={{ color: "var(--color-failed-fg)", fontSize: "var(--text-sm)" }}>{error}</p>
        )}
      </div>
    </Modal>
    {pickerOpen && accountId && (
      <AssetPickerModal
        open={pickerOpen}
        onClose={() => setPickerOpen(false)}
        accountId={accountId}
        needCount={template === "two_panel_contrast" ? 2 : 1}
        onConfirm={(ids) => {
          setPickedAssetIds(ids);
          setPickerOpen(false);
        }}
      />
    )}
    </>
  );
}
