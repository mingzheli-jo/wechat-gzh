import { api } from "./client";

export type ImagePostTemplate = "wechat_image_text";

export type ImagePostStatus =
  | "pending"
  | "generating"
  | "ready"
  | "failed"
  | "publishing"
  | "published";

export interface ImagePost {
  id: string;
  title: string | null;
  template: ImagePostTemplate;
  status: ImagePostStatus;
  error_msg: string | null;
  created_at: string;
  updated_at: string;
}

export interface ImagePostDetail extends ImagePost {
  html_content: string | null;
  style_hint: string | null;
  account_id: string | null;
  wechat_media_id: string | null;
}

export interface ImagePostListPage {
  items: ImagePost[];
  total: number;
}

export interface ImageAsset {
  id: string;
  image_post_id: string;
  sort_order: number;
  alt_text: string | null;
  created_at: string;
}

export interface ImageAssetListPage {
  items: ImageAsset[];
  total: number;
}

export const imagePostsApi = {
  list(params?: { page?: number; page_size?: number; status?: ImagePostStatus }) {
    return api.get<ImagePostListPage>("/image-posts", { params }).then((r) => r.data);
  },
  get(id: string) {
    return api.get<ImagePostDetail>(`/image-posts/${id}`).then((r) => r.data);
  },
  create(body: { title?: string; template?: ImagePostTemplate; style_hint?: string }) {
    return api.post<ImagePostDetail>("/image-posts", body).then((r) => r.data);
  },
  update(id: string, body: { title?: string; style_hint?: string }) {
    return api.patch<ImagePostDetail>(`/image-posts/${id}`, body).then((r) => r.data);
  },
  delete(id: string) {
    return api.delete(`/image-posts/${id}`);
  },
  generate(id: string) {
    return api.post<ImagePostDetail>(`/image-posts/${id}/generate`, {}).then((r) => r.data);
  },
  publish(id: string, body: { account_id: string }) {
    return api.post<ImagePostDetail>(`/image-posts/${id}/publish`, body).then((r) => r.data);
  },
};

export const imageAssetsApi = {
  list(imagePostId: string, params?: { page?: number; page_size?: number }) {
    return api
      .get<ImageAssetListPage>(`/image-posts/${imagePostId}/assets`, { params })
      .then((r) => r.data);
  },
  get(id: string) {
    return api.get<ImageAsset>(`/image-assets/${id}`).then((r) => r.data);
  },
  delete(id: string) {
    return api.delete(`/image-assets/${id}`);
  },
  fileUrl(id: string) {
    return `/api/image-assets/${id}/file`;
  },
};
