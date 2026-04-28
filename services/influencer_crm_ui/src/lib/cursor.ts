export type Cursor = { updatedAt: string; id: number };

export function encodeCursor(updatedAt: string, id: number): string {
  return btoa(JSON.stringify([updatedAt, id]));
}

export function decodeCursor(cursor: string | null | undefined): Cursor | null {
  if (!cursor) return null;
  try {
    const arr = JSON.parse(atob(cursor)) as unknown;
    if (!Array.isArray(arr) || arr.length !== 2) return null;
    const [updatedAt, id] = arr;
    if (typeof updatedAt !== 'string' || typeof id !== 'number') return null;
    return { updatedAt, id };
  } catch {
    return null;
  }
}
