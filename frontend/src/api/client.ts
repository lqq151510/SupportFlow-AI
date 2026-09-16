// 统一 API 客户端：封装 cookie 会话、CSRF 双提交、幂等键与 RFC 9457 错误解析。
//
// 鉴权约定（见后端 PLAN.md / AGENTS.md）：
// - 会话 Cookie `sf_session`：HttpOnly，前端不可读，由浏览器自动随请求携带。
// - CSRF Cookie `sf_csrf`：故意不设 HttpOnly，前端读取后回填到 `X-CSRF-Token` 请求头。
// - 所有写操作必须带 `Idempotency-Key`（≥8 字符）；相同键 + 相同内容重放返回首次结果。
// - 错误统一为 application/problem+json：{ type, title, status, detail, instance, code, request_id }。

const CSRF_COOKIE = "sf_csrf";
const CSRF_HEADER = "X-CSRF-Token";
const IDEMPOTENCY_HEADER = "Idempotency-Key";

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  detail: string | null;
  instance: string | null;
  code: string;
  request_id: string;
}

export class APIError extends Error {
  status: number;
  code: string;
  requestId: string | null;
  detail: string | null;

  constructor(problem: Partial<ProblemDetail>) {
    const message = problem.detail || problem.title || `请求失败（${problem.status}）`;
    super(message);
    this.name = "APIError";
    this.status = problem.status ?? 0;
    this.code = problem.code ?? "unknown";
    this.requestId = problem.request_id ?? null;
    this.detail = problem.detail ?? null;
  }
}

export function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
  return match ? decodeURIComponent(match[1]) : null;
}

export function getCsrfToken(): string | null {
  return getCookie(CSRF_COOKIE);
}

export function genIdempotencyKey(): string {
  // crypto.randomUUID 在受控环境下始终 ≥ 8 字符，满足后端 MIN_IDEMPOTENCY_KEY_LENGTH。
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return "idem-" + Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export interface RequestOptions {
  json?: unknown;
  idempotencyKey?: string;
  signal?: AbortSignal;
}

async function request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const csrf = getCsrfToken();
  if (csrf) headers[CSRF_HEADER] = csrf;
  if (options.idempotencyKey) headers[IDEMPOTENCY_HEADER] = options.idempotencyKey;
  if (options.json !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: options.json !== undefined ? JSON.stringify(options.json) : undefined,
    signal: options.signal,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    const requestId = res.headers.get("X-Request-Id");
    const body = (data ?? {}) as Partial<ProblemDetail>;
    throw new APIError({
      type: body.type,
      title: body.title,
      status: body.status ?? res.status,
      detail: body.detail,
      instance: body.instance,
      code: body.code,
      request_id: body.request_id ?? requestId ?? undefined,
    });
  }

  return data as T;
}

export const api = {
  get: <T>(path: string, opts?: RequestOptions) => request<T>("GET", path, opts),
  post: <T>(path: string, opts?: RequestOptions) => request<T>("POST", path, opts),
  patch: <T>(path: string, opts?: RequestOptions) => request<T>("PATCH", path, opts),
  delete: <T>(path: string, opts?: RequestOptions) => request<T>("DELETE", path, opts),
};

// 文件上传：multipart/form-data，不得设置 Content-Type（浏览器自动补齐 boundary）。
export async function uploadFile<T>(path: string, file: File, idempotencyKey?: string): Promise<T> {
  const form = new FormData();
  form.append("file", file);
  const headers: Record<string, string> = {};
  const csrf = getCsrfToken();
  if (csrf) headers[CSRF_HEADER] = csrf;
  if (idempotencyKey) headers[IDEMPOTENCY_HEADER] = idempotencyKey;

  const res = await fetch(path, {
    method: "POST",
    headers,
    credentials: "include",
    body: form,
  });

  const text = await res.text();
  let data: unknown = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }
  if (!res.ok) {
    const body = (data ?? {}) as Partial<ProblemDetail>;
    throw new APIError({
      status: body.status ?? res.status,
      code: body.code ?? "unknown",
      detail: body.detail,
      request_id: body.request_id ?? res.headers.get("X-Request-Id") ?? undefined,
      title: body.title,
    });
  }
  return data as T;
}
