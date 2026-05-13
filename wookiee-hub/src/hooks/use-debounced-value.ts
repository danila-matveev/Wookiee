import { useEffect, useState } from "react"

/**
 * useDebouncedValue — возвращает значение с задержкой.
 *
 * Используется в поисковых инпутах реестров каталога (W9.3), чтобы
 * не перефильтровывать список из тысяч строк на каждый keystroke.
 * При смене `value` дебаунс сбрасывает прошлый таймер и стартует новый.
 *
 * @param value — исходное значение
 * @param delayMs — задержка в миллисекундах (по умолчанию 300)
 */
export function useDebouncedValue<T>(value: T, delayMs = 300): T {
  const [debounced, setDebounced] = useState<T>(value)
  useEffect(() => {
    const t = window.setTimeout(() => setDebounced(value), delayMs)
    return () => window.clearTimeout(t)
  }, [value, delayMs])
  return debounced
}
