// ---------------------------------------------------------------------------
// Typed fetch wrapper for the WookieeHub API
// ---------------------------------------------------------------------------

const BASE_URL = import.meta.env.VITE_API_URL ?? ""

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = "ApiError"
    this.status = status
  }
}

/**
 * Generic GET helper.
 * Automatically appends query params and parses the JSON response.
 */
export async function get<T>(
  path: string,
  params?: Record<string, string | number | undefined>,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, BASE_URL || window.location.origin)

  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") {
        url.searchParams.set(key, String(value))
      }
    }
  }

  const res = await fetch(url.toString(), { signal })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }

  return res.json() as Promise<T>
}

/**
 * Generic POST helper.
 * Sends JSON body and parses the JSON response.
 */
export async function post<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, BASE_URL || window.location.origin)

  const res = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })

  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }

  return res.json() as Promise<T>
}

/**
 * Generic PATCH helper.
 * Sends JSON body and parses the JSON response.
 */
export async function patch<T>(
  path: string,
  body: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const url = new URL(path, BASE_URL || window.location.origin)
  const res = await fetch(url.toString(), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }
  return res.json() as Promise<T>
}

/**
 * Generic DELETE helper.
 * Returns undefined for 204 No Content responses.
 */
export async function httpDelete(
  path: string,
  signal?: AbortSignal,
): Promise<void> {
  const url = new URL(path, BASE_URL || window.location.origin)
  const res = await fetch(url.toString(), {
    method: "DELETE",
    signal,
  })
  if (!res.ok) {
    const text = await res.text().catch(() => res.statusText)
    throw new ApiError(res.status, text)
  }
}

/**
 * DELETE with custom headers and JSON response.
 * Used for two-step delete with math challenge.
 */
export async function httpDeleteJson<T>(
  path: string,
  headers?: Record<string, string>,
  signal?: AbortSignal,
): Promise<{ status: number; data: T }> {
  const url = new URL(path, BASE_URL || window.location.origin)
  const res = await fetch(url.toString(), {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
      ...headers,
    },
    signal,
  })

  const data = await res.json() as T
  return { status: res.status, data }
}
