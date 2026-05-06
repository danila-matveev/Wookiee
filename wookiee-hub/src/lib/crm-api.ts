import { supabase } from "@/lib/supabase"

const getBase = (): string => import.meta.env.VITE_CRM_API_URL ?? "https://crm.matveevdanila.com/api"

export class CrmApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message: string,
  ) {
    super(message)
  }
}

const etagCache = new Map<string, { etag: string; body: unknown }>()

async function getAuthHeader(): Promise<string> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token
  if (!token) throw new CrmApiError(401, null, "No active session — please log in again")
  return `Bearer ${token}`
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${getBase()}${path}`
  const cached = method === "GET" ? etagCache.get(url) : undefined
  const headers: Record<string, string> = {
    Authorization: await getAuthHeader(),
    "Content-Type": "application/json",
  }
  if (cached) headers["If-None-Match"] = cached.etag

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })

  if (res.status === 304 && cached) {
    return cached.body as T
  }

  if (!res.ok) {
    let payload: unknown = null
    try { payload = await res.json() } catch { /* empty */ }
    throw new CrmApiError(res.status, payload, `${method} ${path} → ${res.status}`)
  }

  if (res.status === 204) return undefined as T

  const json = (await res.json()) as T
  if (method === "GET") {
    const etag = res.headers.get("etag")
    if (etag) etagCache.set(url, { etag, body: json })
  } else {
    const family = url.replace(/\/\d+$/, "").split("?")[0]
    for (const k of etagCache.keys()) {
      if (k.startsWith(family)) etagCache.delete(k)
    }
  }
  return json
}

export const crmApi = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T = void>(path: string) => request<T>("DELETE", path),
}
