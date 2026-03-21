/**
 * Утилиты для форматирования данных
 */

export function formatApiResponse<T>(data: T, metadata?: Record<string, unknown>): {
  content: Array<{ type: 'text'; text: string }>;
} {
  const formattedData = {
    data,
    ...(metadata && { metadata }),
  };
  return {
    content: [{ type: 'text', text: JSON.stringify(formattedData, null, 2) }],
  };
}

export function formatError(error: Error | unknown, context?: string): {
  content: Array<{ type: 'text'; text: string }>;
  isError: true;
} {
  const errorMessage = error instanceof Error ? error.message : String(error);
  const formattedError = {
    error: errorMessage,
    ...(context && { context }),
  };
  return {
    content: [{ type: 'text', text: JSON.stringify(formattedError, null, 2) }],
    isError: true,
  };
}
