import { api } from "./client";

export type CreationStatus =
  | "pending"
  | "extracting"
  | "retrieving"
  | "generating"
  | "reviewing"
  | "done"
  | "failed";

export type CreationInputMode = "link" | "manual";

export interface RetrievedSource {
  library_item_id: string;
  title: string | null;
  source_url: string | null;
  relevance: number;
  excerpt: string;
}

export interface FactCheck {
  // null when generated in no-source mode (mode === "no_sources").
  score: number | null;
  mode?: "no_sources";
  unsupported_claims: string[];
  issues: string[];
  note?: string;
  error?: boolean;
}

export interface Creation {
  id: string;
  input_mode: CreationInputMode;
  source_url: string | null;
  source_title: string | null;
  extracted_theme: string | null;
  generated_title: string | null;
  status: CreationStatus;
  error_msg: string | null;
  account_id: string | null;
  created_at: string;
}

export interface CreationDetail extends Creation {
  source_text_snapshot: string | null;
  keywords: string[] | null;
  retrieved_sources: RetrievedSource[] | null;
  generated_content_md: string | null;
  generated_content_html: string | null;
  fact_check: FactCheck | null;
}

export interface CreationListPage {
  items: Creation[];
  total: number;
}

export interface CreateCreationPayload {
  source_url?: string;
  theme?: string;
  account_id?: string;
}

export interface CreationEditPayload {
  generated_title?: string;
  generated_content_html?: string;
}

export const creationsApi = {
  create(payload: CreateCreationPayload) {
    return api.post<Creation>("/creations", payload).then((r) => r.data);
  },
  list(params: { status?: CreationStatus; page?: number; page_size?: number } = {}) {
    return api
      .get<CreationListPage>("/creations", { params })
      .then((r) => r.data);
  },
  get(id: string) {
    return api.get<CreationDetail>(`/creations/${id}`).then((r) => r.data);
  },
  update(id: string, payload: CreationEditPayload) {
    return api
      .patch<CreationDetail>(`/creations/${id}`, payload)
      .then((r) => r.data);
  },
  regenerate(id: string) {
    return api.post<Creation>(`/creations/${id}/regenerate`).then((r) => r.data);
  },
  remove(id: string) {
    return api.delete(`/creations/${id}`).then((r) => r.data);
  },
};
