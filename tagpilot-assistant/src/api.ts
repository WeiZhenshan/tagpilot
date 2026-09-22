const TOKEN_COOKIE = "Admin-Token";
const API_PREFIX = "/dev-api";

export class ApiError extends Error {
  status: number;
  code?: number;
  constructor(message: string, status: number, code?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function readAdminToken(): string | undefined {
  const parts = document.cookie.split(";");
  for (const part of parts) {
    const [name, ...rest] = part.trim().split("=");
    if (name === TOKEN_COOKIE) {
      return decodeURIComponent(rest.join("="));
    }
  }
  return undefined;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = readAdminToken();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", "Bearer " + token);
  }
  const response = await fetch(API_PREFIX + path, { ...init, headers });
  if (readAdminToken() !== token) {
    window.dispatchEvent(new Event("tagpilot-agent:session-changed"));
    throw new ApiError("登录用户已变更，请刷新工作台。", 401, 401);
  }
  if (response.status === 401) {
    throw new ApiError("登录已过期，请重新登录。", 401, 401);
  }
  const payload = await response.json().catch(() => ({}));
  const code =
    typeof payload.code === "number"
      ? payload.code
      : response.ok
      ? 200
      : response.status;
  if (code === 401) {
    throw new ApiError(payload.msg || "登录已过期，请重新登录。", 401, 401);
  }
  if (!response.ok || code !== 200) {
    throw new ApiError(payload.msg || "请求失败", response.status, code);
  }
  return payload as T;
}

export type LibraryRow = {
  libraryId: number;
  libraryName: string;
};

export type AjaxList<T> = {
  rows?: T[];
  total?: number;
  data?: T;
};

export type AjaxData<T> = {
  data?: T;
  msg?: string;
};

export function listLibraries(): Promise<AjaxList<LibraryRow>> {
  return apiRequest("/taglibrary/library/list?pageNum=1&pageSize=100");
}

export type Candidate = {
  tag_id?: number;
  name?: string;
  family_key?: string;
  code?: string;
};

export type RetrieveResult = {
  decision?: string;
  selector?: string;
  model_connected?: boolean;
  confidence?: number | null;
  explanation?: string | null;
  recommended_tag_ids?: number[];
  dsl?: unknown;
  dsl_valid?: boolean;
  validation_error?: string | null;
  candidates?: Candidate[];
  auto_execute?: boolean;
  requires_confirmation?: boolean;
  trace_id?: string;
  snapshot_id?: string;
  build_id?: string;
};

export function retrieveSemantic(
  libraryId: number,
  requirement: string,
  signal?: AbortSignal
): Promise<AjaxData<RetrieveResult>> {
  return apiRequest("/taglibrary/semantic/retrieve", {
    method: "POST",
    body: JSON.stringify({ libraryId: String(libraryId), requirement }),
    signal,
  });
}

export function submitFeedback(payload: {
  traceId?: string;
  buildId?: string;
  snapshotId?: string;
  recommendedTagId?: number;
  finalTagId?: number;
  action: string;
}): Promise<unknown> {
  return apiRequest("/taglibrary/semantic/feedback", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
