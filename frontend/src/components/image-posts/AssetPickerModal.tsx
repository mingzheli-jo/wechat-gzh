import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { imageAssetsApi, type ImageAsset } from "../../api/image-posts";
import { Button, Modal, PageSpinner } from "../ui";

interface Props {
  open: boolean;
  onClose: () => void;
  accountId: string;
  needCount: number;
  onConfirm: (assetIds: string[]) => void;
}

export function AssetPickerModal({ open, onClose, accountId, needCount, onConfirm }: Props) {
  const [selected, setSelected] = useState<string[]>([]);

  const assets = useQuery({
    queryKey: ["image-assets", accountId],
    queryFn: async () => imageAssetsApi.list({ account_id: accountId }),
    enabled: Boolean(accountId) && open,
  });

  function toggle(id: string) {
    if (selected.includes(id)) {
      setSelected(selected.filter((s) => s !== id));
    } else if (selected.length < needCount) {
      setSelected([...selected, id]);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={`从图库选 ${needCount} 张`}
      description={`已选 ${selected.length}/${needCount}`}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={selected.length !== needCount}
            onClick={() => onConfirm(selected)}
          >
            确认
          </Button>
        </>
      }
    >
      {assets.isLoading ? (
        <PageSpinner />
      ) : !assets.data || assets.data.items.length === 0 ? (
        <p>该账号还没有可复用的图。</p>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(140px, 1fr))", gap: "var(--space-3)" }}>
          {assets.data.items.map((a: ImageAsset) => {
            const isSelected = selected.includes(a.id);
            const order = selected.indexOf(a.id);
            return (
              <div
                key={a.id}
                onClick={() => toggle(a.id)}
                style={{
                  position: "relative",
                  cursor: "pointer",
                  border: isSelected ? "3px solid var(--color-ink)" : "1px solid var(--color-surface-3)",
                  borderRadius: "var(--radius-md)",
                  overflow: "hidden",
                  aspectRatio: "1 / 1",
                }}
              >
                <img
                  src={imageAssetsApi.fileUrl(a.id)}
                  alt={a.scene_prompt ?? ""}
                  style={{ width: "100%", height: "100%", objectFit: "cover" }}
                />
                {isSelected && (
                  <div style={{
                    position: "absolute", top: 4, left: 4,
                    width: 24, height: 24, borderRadius: "50%",
                    background: "var(--color-ink)", color: "white",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 12, fontWeight: "bold",
                  }}>
                    {order + 1}
                  </div>
                )}
                <div style={{
                  position: "absolute", bottom: 0, left: 0, right: 0,
                  background: "rgba(0,0,0,0.6)", color: "white",
                  fontSize: 10, padding: "2px 6px",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>
                  {a.scene_prompt}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Modal>
  );
}
