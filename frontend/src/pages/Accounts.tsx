import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api/client";
import {
  Badge,
  Button,
  Card,
  ConfirmModal,
  EmptyState,
  Input,
  Modal,
  PageSpinner,
  Textarea,
} from "../components/ui";

type Account = {
  id: string;
  name: string;
  wechat_appid: string;
  category: string;
  title_prompt: string | null;
  content_prompt: string | null;
  style_desc: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

type AccountFormData = {
  name: string;
  wechat_appid: string;
  wechat_secret: string;
  category: string;
  title_prompt: string;
  content_prompt: string;
  style_desc: string;
};

const EMPTY_FORM: AccountFormData = {
  name: "",
  wechat_appid: "",
  wechat_secret: "",
  category: "",
  title_prompt: "",
  content_prompt: "",
  style_desc: "",
};

type FormErrors = Partial<Record<keyof AccountFormData, string>>;

function validateForm(data: AccountFormData, isEdit: boolean): FormErrors {
  const errors: FormErrors = {};
  if (!data.name.trim()) errors.name = "名称不能为空";
  if (!data.wechat_appid.trim()) errors.wechat_appid = "AppID 不能为空";
  if (!isEdit && !data.wechat_secret.trim()) errors.wechat_secret = "AppSecret 不能为空（创建时必填）";
  if (!data.category.trim()) errors.category = "分类不能为空";
  return errors;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
}

// ---- Account Form Modal ----

interface AccountFormModalProps {
  open: boolean;
  onClose: () => void;
  initial?: Account | null;
  onSaved: () => void;
}

function AccountFormModal({ open, onClose, initial, onSaved }: AccountFormModalProps) {
  const isEdit = Boolean(initial);
  const [form, setForm] = useState<AccountFormData>(() =>
    initial
      ? {
          name: initial.name,
          wechat_appid: initial.wechat_appid,
          wechat_secret: "",
          category: initial.category,
          title_prompt: initial.title_prompt ?? "",
          content_prompt: initial.content_prompt ?? "",
          style_desc: initial.style_desc ?? "",
        }
      : EMPTY_FORM
  );
  const [errors, setErrors] = useState<FormErrors>({});

  function set(field: keyof AccountFormData, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  }

  const save = useMutation({
    mutationFn: async () => {
      const payload: Record<string, unknown> = {
        name: form.name,
        wechat_appid: form.wechat_appid,
        category: form.category,
        title_prompt: form.title_prompt || null,
        content_prompt: form.content_prompt || null,
        style_desc: form.style_desc || null,
      };
      if (!isEdit || form.wechat_secret) {
        payload.wechat_secret = form.wechat_secret;
      }
      if (isEdit && initial) {
        return api.patch(`/accounts/${initial.id}`, payload);
      }
      return api.post("/accounts", payload);
    },
    onSuccess: () => {
      onSaved();
      onClose();
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const errs = validateForm(form, isEdit);
    if (Object.keys(errs).length > 0) {
      setErrors(errs);
      return;
    }
    save.mutate();
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={isEdit ? "编辑公众号" : "新增公众号"}
      description={isEdit ? `正在编辑「${initial?.name}」` : "填写公众号信息后点击保存"}
      size="md"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={save.isPending}>
            取消
          </Button>
          <Button
            variant="primary"
            onClick={handleSubmit as unknown as React.MouseEventHandler}
            loading={save.isPending}
          >
            {isEdit ? "保存修改" : "创建公众号"}
          </Button>
        </>
      }
    >
      <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "var(--space-4)" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "var(--space-3)" }}>
          <Input
            label="公众号名称"
            value={form.name}
            onChange={(e) => set("name", e.target.value)}
            placeholder="例：育儿新知"
            error={errors.name}
            required
          />
          <Input
            label="分类"
            value={form.category}
            onChange={(e) => set("category", e.target.value)}
            placeholder="例：母婴"
            error={errors.category}
            required
          />
        </div>

        <Input
          label="AppID"
          value={form.wechat_appid}
          onChange={(e) => set("wechat_appid", e.target.value)}
          placeholder="wx1234567890abcdef"
          error={errors.wechat_appid}
          required
          style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}
        />

        <Input
          label={isEdit ? "AppSecret（留空则不更新）" : "AppSecret"}
          type="password"
          value={form.wechat_secret}
          onChange={(e) => set("wechat_secret", e.target.value)}
          placeholder={isEdit ? "输入新的 Secret 才会更新" : "粘贴 AppSecret"}
          error={errors.wechat_secret}
          hint={isEdit ? "出于安全原因，Secret 从不回显" : undefined}
          style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-sm)" }}
        />

        <Textarea
          label="标题改写提示词"
          value={form.title_prompt}
          onChange={(e) => set("title_prompt", e.target.value)}
          placeholder="可选：告诉 AI 如何改写标题，例如「保持原意但增强吸引力」"
          rows={3}
        />

        <Textarea
          label="正文改写提示词"
          value={form.content_prompt}
          onChange={(e) => set("content_prompt", e.target.value)}
          placeholder="可选：告诉 AI 改写正文时的风格要求"
          rows={3}
        />

        <Input
          label="风格描述"
          value={form.style_desc}
          onChange={(e) => set("style_desc", e.target.value)}
          placeholder="可选：一句话描述目标风格，例如「轻松口语化，适合宝妈」"
        />

        {save.isError && (
          <div
            style={{
              padding: "var(--space-3)",
              backgroundColor: "var(--color-failed)",
              color: "var(--color-failed-fg)",
              borderRadius: "var(--radius-md)",
              fontSize: "var(--text-sm)",
            }}
          >
            保存失败，请检查填写内容后重试
          </div>
        )}
      </form>
    </Modal>
  );
}

// ---- Main page ----

export default function Accounts() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<Account | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Account | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["accounts"],
    queryFn: async () => (await api.get<Account[]>("/accounts")).data,
  });

  const toggleActive = useMutation({
    mutationFn: async ({ id, is_active }: { id: string; is_active: boolean }) =>
      api.patch(`/accounts/${id}`, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });

  const deleteAccount = useMutation({
    mutationFn: async (id: string) => api.delete(`/accounts/${id}`),
    onSuccess: () => {
      setDeleteTarget(null);
      qc.invalidateQueries({ queryKey: ["accounts"] });
    },
  });

  function openCreate() {
    setEditTarget(null);
    setModalOpen(true);
  }

  function openEdit(account: Account) {
    setEditTarget(account);
    setModalOpen(true);
  }

  function onSaved() {
    qc.invalidateQueries({ queryKey: ["accounts"] });
    qc.invalidateQueries({ queryKey: ["accounts-min"] });
  }

  return (
    <div
      style={{
        maxWidth: "var(--max-content)",
        margin: "0 auto",
        padding: "var(--space-8)",
      }}
    >
      {/* Page header */}
      <div
        style={{
          display: "flex",
          alignItems: "flex-start",
          justifyContent: "space-between",
          marginBottom: "var(--space-8)",
          gap: "var(--space-4)",
        }}
      >
        <div>
          <h1
            style={{
              fontSize: "var(--text-xl)",
              fontWeight: "var(--weight-semi)",
              color: "var(--color-ink)",
              letterSpacing: "-0.02em",
              margin: 0,
            }}
          >
            公众号管理
          </h1>
          <p
            style={{
              fontSize: "var(--text-sm)",
              color: "var(--color-ink-3)",
              marginTop: "var(--space-1)",
            }}
          >
            管理改写目标公众号及其 AI 改写配置
          </p>
        </div>
        <Button onClick={openCreate} style={{ flexShrink: 0 }}>
          新增公众号
        </Button>
      </div>

      {/* List */}
      {isLoading ? (
        <PageSpinner />
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={
            <svg width="40" height="40" viewBox="0 0 40 40" fill="none">
              <rect x="6" y="10" width="28" height="22" rx="3" stroke="currentColor" strokeWidth="1.5" />
              <circle cx="20" cy="21" r="5" stroke="currentColor" strokeWidth="1.5" />
              <path d="M6 16h28" stroke="currentColor" strokeWidth="1.5" />
            </svg>
          }
          title="还没有公众号"
          description="点击右上角「新增公众号」开始配置"
          action={<Button onClick={openCreate}>新增公众号</Button>}
        />
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(340px, 1fr))",
            gap: "var(--space-4)",
          }}
        >
          {data.map((account, i) => (
            <Card
              key={account.id}
              padding="md"
              style={{
                display: "flex",
                flexDirection: "column",
                gap: "var(--space-3)",
                opacity: account.is_active ? 1 : 0.6,
                animation: `fade-in var(--dur-normal) ${i * 40}ms var(--ease-out) both`,
              }}
            >
              {/* Card header */}
              <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "var(--space-3)" }}>
                <div style={{ minWidth: 0 }}>
                  <h3
                    style={{
                      fontSize: "var(--text-base)",
                      fontWeight: "var(--weight-semi)",
                      color: "var(--color-ink)",
                      margin: 0,
                      lineHeight: "var(--leading-snug)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {account.name}
                  </h3>
                  <p
                    style={{
                      fontSize: "var(--text-xs)",
                      color: "var(--color-ink-3)",
                      fontFamily: "var(--font-mono)",
                      marginTop: "var(--space-1)",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}
                  >
                    {account.wechat_appid}
                  </p>
                </div>
                <Badge variant={account.is_active ? "done" : "default"} className="flex-shrink-0">
                  {account.is_active ? "启用" : "停用"}
                </Badge>
              </div>

              {/* Meta */}
              <div
                style={{
                  display: "flex",
                  gap: "var(--space-2)",
                  flexWrap: "wrap",
                }}
              >
                <Badge variant="outline">{account.category}</Badge>
              </div>

              {/* Prompts preview */}
              {(account.title_prompt || account.content_prompt || account.style_desc) && (
                <div
                  style={{
                    padding: "var(--space-3)",
                    backgroundColor: "var(--color-surface-2)",
                    borderRadius: "var(--radius-md)",
                    display: "flex",
                    flexDirection: "column",
                    gap: "var(--space-2)",
                  }}
                >
                  {account.style_desc && (
                    <p
                      style={{
                        fontSize: "var(--text-xs)",
                        color: "var(--color-ink-2)",
                        margin: 0,
                        lineHeight: "var(--leading-snug)",
                        display: "-webkit-box",
                        WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical",
                        overflow: "hidden",
                      }}
                    >
                      {account.style_desc}
                    </p>
                  )}
                </div>
              )}

              {/* Footer */}
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  borderTop: "1px solid var(--color-surface-2)",
                  paddingTop: "var(--space-3)",
                  marginTop: "auto",
                }}
              >
                <span style={{ fontSize: "var(--text-xs)", color: "var(--color-ink-4)" }}>
                  创建于 {formatDate(account.created_at)}
                </span>
                <div style={{ display: "flex", gap: "var(--space-2)" }}>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() =>
                      toggleActive.mutate({
                        id: account.id,
                        is_active: !account.is_active,
                      })
                    }
                  >
                    {account.is_active ? "停用" : "启用"}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={() => openEdit(account)}>
                    编辑
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => setDeleteTarget(account)}
                    style={{ color: "var(--color-failed-fg)" }}
                  >
                    删除
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create / Edit modal */}
      <AccountFormModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        initial={editTarget}
        onSaved={onSaved}
      />

      {/* Delete confirmation */}
      <ConfirmModal
        open={Boolean(deleteTarget)}
        onClose={() => setDeleteTarget(null)}
        onConfirm={() => deleteTarget && deleteAccount.mutate(deleteTarget.id)}
        loading={deleteAccount.isPending}
        title="删除公众号"
        message={`确认删除「${deleteTarget?.name}」？此操作不可撤销，相关草稿不受影响。`}
        confirmLabel="确认删除"
      />
    </div>
  );
}
