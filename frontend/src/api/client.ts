const BASE_URL = "/api";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly code?: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function throwApiError(res: Response): Promise<never> {
  let detail = res.statusText;
  let code: string | undefined;
  try {
    const body = await res.json();
    detail = body.detail ?? detail;
    code = body.code;
  } catch {
    // ignore parse errors
  }
  throw new ApiError(res.status, detail, code);
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) {
    return throwApiError(res);
  }
  return res.json() as Promise<T>;
}

export async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    return throwApiError(res);
  }
  return res.json() as Promise<T>;
}

export async function del(path: string): Promise<void> {
  const res = await fetch(`${BASE_URL}${path}`, { method: "DELETE" });
  if (!res.ok) {
    return throwApiError(res);
  }
}
