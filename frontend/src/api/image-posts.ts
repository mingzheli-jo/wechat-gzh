import { api } from "./client";

export type ImagePostTemplate = "two_panel_contrast" | "single_panel_caption";

export type ImagePostStatus =
  | "pending"
  | "generating"
  | "generated"
  | "composing"
  | "pushing"
  | "pushed"
  | "failed";

export interface ImagePost {
  id: string;
  account_id: string;
  template: ImagePostTemplate;
  topic: string;
  tone: string | null;
  status: ImagePostStatus;
  error_msg: string | null;
  wechat_pushed_at: string | null;
  created_at: string;
}

export interface ImagePostDetail extends ImagePost {
  captions: string[] | null;
  panel_prompts: string[] | null;
  asset_ids: string[] | null;
  panel_asset_ids: string[] | null;
  composed_image_path: string | null;
  wechat_thumb_media_id: string | null;
  wechat_draft_media_id: string | null;
}

export interface ImagePostListPage {
  items: ImagePost[];
  total: number;
}

export interface ImageAsset {
  id: string;
  account_id: string;
  image_path: string;
  scene_prompt: string | null;
  tags: string[] | null;
  source: string;
  used_count: number;
  created_at: string;
}

export interface ImageAssetListPage {
  items: ImageAsset[];
  total: number;
}

export const imagePostsApi = {
  list(params?: {
    account_id?: string;
    status?: ImagePostStatus;
    page?: number;
    page_size?: number;
  }) {
    return api.get<ImagePostListPage>("/image-posts", { params }).then((r) => r.data);
  },
  get(id: string) {
    return api.get<ImagePostDetail>(`/image-posts/${id}`).then((r) => r.data);
  },
  create(body: {
    account_id: string;
    template: ImagePostTemplate;
    topic: string;
    tone?: string | null;
    panel_asset_ids?: string[] | null;
  }) {
    return api.post<ImagePost>("/image-posts", body).then((r) => r.data);
  },
  patch(id: string, body: { captions: string[] }) {
    return api.patch<ImagePostDetail>(`/image-posts/${id}`, body).then((r) => r.data);
  },
  regenerateCaptions(id: string) {
    return api
      .post<ImagePostDetail>(`/image-posts/${id}/regenerate-captions`)
      .then((r) => r.data);
  },
  regenerate(id: string) {
    return api.post<ImagePost>(`/image-posts/${id}/regenerate`).then((r) => r.data);
  },
  push(id: string) {
    return api.post<ImagePost>(`/image-posts/${id}/push-to-wechat`).then((r) => r.data);
  },
  delete(id: string) {
    return api.delete(`/image-posts/${id}`);
  },
};

export const imageAssetsApi = {
  list(params: { account_id: string; page?: number; page_size?: number }) {
    return api
      .get<ImageAssetListPage>("/image-assets", { params })
      .then((r) => r.data);
  },
  get(id: string) {
    return api.get<ImageAsset>(`/image-assets/${id}`).then((r) => r.data);
  },
  fileUrl(id: string) {
    return `/api/image-assets/${id}/file`;
  },
};
