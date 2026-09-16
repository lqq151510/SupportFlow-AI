// 类型化的 API 端点封装。Schema 类型由 openapi-typescript 从 docs/contracts/openapi.json 生成，
// 前端不得手写重复定义（AGENTS.md §8 / PLAN.md「前端设计」）。
import type { components } from "./types";
import { api, uploadFile } from "./client";

// ---- Schema 类型别名 ----
export type PrincipalOut = components["schemas"]["PrincipalOut"];
export type TicketOut = components["schemas"]["TicketOut"];
export type TicketDetailOut = components["schemas"]["TicketDetailOut"];
export type TicketPageOut = components["schemas"]["TicketPageOut"];
export type DraftDetailOut = components["schemas"]["DraftDetailOut"];
export type RunOut = components["schemas"]["RunOut"];
export type RunListOut = components["schemas"]["RunListOut"];
export type ActionRequestOut = components["schemas"]["ActionRequestOut"];
export type ActionRequestListOut = components["schemas"]["ActionRequestListOut"];
export type ActionDecisionOut = components["schemas"]["ActionDecisionOut"];
export type ImportJobOut = components["schemas"]["ImportJobOut"];
export type SearchPageOut = components["schemas"]["SearchPageOut"];
export type ModelConfigOut = components["schemas"]["ModelConfigOut"];
export type ModelConfigListOut = components["schemas"]["ModelConfigListOut"];
export type ModelConfigCreateIn = components["schemas"]["ModelConfigCreateIn"];
export type ModelConfigUpdateIn = components["schemas"]["ModelConfigUpdateIn"];
export type ModelCapability = components["schemas"]["ModelCapability"];
export type ConnectionTestOut = components["schemas"]["ConnectionTestOut"];
export type EvaluationImportOut = components["schemas"]["EvaluationImportOut"];
export type EvaluationRunOut = components["schemas"]["EvaluationRunOut"];
export type EvaluationRunCreateIn = components["schemas"]["EvaluationRunCreateIn"];
export type TicketStatus = components["schemas"]["TicketStatus"];

const V1 = "/api/v1";

export const authApi = {
  login: (email: string, password: string) =>
    api.post<PrincipalOut>(`${V1}/auth/login`, { json: { email, password } }),
  logout: () => api.post<void>(`${V1}/auth/logout`),
  me: () => api.get<PrincipalOut>(`${V1}/auth/me`),
};

export const ticketApi = {
  list: (params: { status?: TicketStatus | null; limit?: number; offset?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.limit != null) qs.set("limit", String(params.limit));
    if (params.offset != null) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return api.get<TicketPageOut>(`${V1}/tickets${q ? `?${q}` : ""}`);
  },
  submit: (body: { subject: string; body: string; model_mode?: string | null }, idempotencyKey: string) =>
    api.post<unknown>(`${V1}/tickets`, { json: body, idempotencyKey }),
  get: (id: string) => api.get<TicketDetailOut>(`${V1}/tickets/${id}`),
  listDrafts: (id: string) => api.get<DraftDetailOut[]>(`${V1}/tickets/${id}/drafts`),
  editDraft: (ticketId: string, draftId: string, content: string, idempotencyKey: string) =>
    api.patch<DraftDetailOut>(`${V1}/tickets/${ticketId}/drafts/${draftId}`, {
      json: { content },
      idempotencyKey,
    }),
  publishDraft: (ticketId: string, draftId: string, idempotencyKey: string) =>
    api.post<DraftDetailOut>(`${V1}/tickets/${ticketId}/drafts/${draftId}/publish`, {
      idempotencyKey,
    }),
  listRuns: (id: string) => api.get<RunListOut>(`${V1}/tickets/${id}/runs`),
  startRun: (id: string, model_mode: string | null, idempotencyKey: string) =>
    api.post<RunOut>(`${V1}/tickets/${id}/runs`, {
      json: model_mode ? { model_mode } : {},
      idempotencyKey,
    }),
};

export const runApi = {
  get: (id: string) => api.get<RunOut>(`${V1}/runs/${id}`),
};

export const approvalApi = {
  list: (params: { status?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.status) qs.set("status", params.status);
    if (params.limit != null) qs.set("limit", String(params.limit));
    const q = qs.toString();
    return api.get<ActionRequestListOut>(`${V1}/action-requests${q ? `?${q}` : ""}`);
  },
  get: (id: string) => api.get<ActionRequestOut>(`${V1}/action-requests/${id}`),
  decide: (id: string, approve: boolean, idempotencyKey: string) =>
    api.post<ActionDecisionOut>(`${V1}/action-requests/${id}/decide`, {
      json: { approve },
      idempotencyKey,
    }),
};

export const knowledgeApi = {
  importDocument: (file: File, idempotencyKey: string) =>
    uploadFile<ImportJobOut>(`${V1}/knowledge/imports`, file, idempotencyKey),
  importHistory: (file: File, idempotencyKey: string) =>
    uploadFile<ImportJobOut>(`${V1}/history/imports`, file, idempotencyKey),
  search: (query: string, limit = 20) => {
    const qs = new URLSearchParams({ query, limit: String(limit) });
    return api.get<SearchPageOut>(`${V1}/knowledge/search?${qs.toString()}`);
  },
};

export const modelApi = {
  list: () => api.get<ModelConfigListOut>(`${V1}/model-configs`),
  create: (body: ModelConfigCreateIn) => api.post<ModelConfigOut>(`${V1}/model-configs`, { json: body }),
  update: (id: string, body: ModelConfigUpdateIn) =>
    api.patch<ModelConfigOut>(`${V1}/model-configs/${id}`, { json: body }),
  enable: (id: string) => api.post<ModelConfigOut>(`${V1}/model-configs/${id}/enable`),
  test: (id: string) => api.post<ConnectionTestOut>(`${V1}/model-configs/${id}/test`),
};

export const evaluationApi = {
  importCases: () => api.post<EvaluationImportOut>(`${V1}/evaluations/import`),
  createRun: (body: EvaluationRunCreateIn) =>
    api.post<EvaluationRunOut>(`${V1}/evaluations/runs`, { json: body }),
  getRun: (id: string) => api.get<EvaluationRunOut>(`${V1}/evaluations/runs/${id}`),
  reportUrl: (id: string) => `${V1}/evaluations/runs/${id}/report`,
};
