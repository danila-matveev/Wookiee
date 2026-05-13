// W9.18 — единый wrapper для toast-уведомлений в каталоге.
//
// Поверх `sonner`. Все ошибки CRUD-операций каталога идут через `toast.error`
// (вместо `window.alert(translateError(e))`, который был раньше). Texts уже
// переведены через `error-translator.ts`, здесь только показ.
//
// API:
//   import { toast } from "@/lib/catalog/toast"
//   toast.error(translateError(e))
//   toast.success("Сохранено")
//   toast.info("…")
//   toast.warning("…")
//
// Toaster подключается в `src/main.tsx` (одна точка на всё приложение).

import { toast as sonnerToast } from "sonner"

export const toast = sonnerToast

export type ToastFn = typeof sonnerToast
