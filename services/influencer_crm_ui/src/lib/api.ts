// Read env at call time (not at module load) so tests that stub
// `import.meta.env` between imports and the first call see the override.
// In production this is a single property access — negligible cost.
const getBase = (): string => import.meta.env.VITE_API_BASE_URL ?? '/api';
const getKey = (): string => import.meta.env.VITE_API_KEY ?? '';

export class ApiError extends Error {
  constructor(
    public status: number,
    public body: unknown,
    message: string,
  ) {
    super(message);
  }
}

const etagCache = new Map<string, { etag: string; body: unknown }>();

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const url = `${getBase()}${path}`;
  const cached = method === 'GET' ? etagCache.get(url) : undefined;
  const headers: Record<string, string> = {
    'X-API-Key': getKey(),
    'Content-Type': 'application/json',
  };
  if (cached) headers['If-None-Match'] = cached.etag;

  const res = await fetch(url, {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 304 && cached) {
    return cached.body as T;
  }

  if (!res.ok) {
    let payload: unknown = null;
    try {
      payload = await res.json();
    } catch {
      /* empty body */
    }
    throw new ApiError(res.status, payload, `${method} ${path} → ${res.status}`);
  }

  if (res.status === 204) return undefined as T;

  const json = (await res.json()) as T;
  if (method === 'GET') {
    const etag = res.headers.get('etag');
    if (etag) etagCache.set(url, { etag, body: json });
  } else {
    // Mutation invalidates the whole resource family — both detail (`/bloggers/1`)
    // and list (`/bloggers`) entries. We strip a trailing `/{id}` segment from the
    // mutated URL to derive the family root, then evict any cache key that starts
    // with it. Plain `startsWith(url)` would miss the list cache when only the
    // detail URL was hit (e.g. PATCH /bloggers/1 wouldn't invalidate /bloggers).
    const family = url.replace(/\/\d+$/, '').split('?')[0];
    for (const k of etagCache.keys()) {
      if (k.startsWith(family)) etagCache.delete(k);
    }
  }
  return json;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T = void>(path: string) => request<T>('DELETE', path),
};
