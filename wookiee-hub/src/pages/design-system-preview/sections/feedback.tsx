import { Box, Search } from "lucide-react"
import { Button, Skeleton } from "@/components/ui-v2/primitives"
import { Alert, EmptyState, useToast } from "@/components/ui-v2/feedback"
import { Demo, SubSection } from "../shared"

/**
 * FeedbackSection — canonical reference: `foundation.jsx:2523-2592`.
 *
 * Toast/Alert/EmptyState/Skeleton.
 * - Toast triggers fire the global store-backed ToastProvider (mounted in
 *   `src/main.tsx`), so the actual toasts appear in the bottom-right
 *   viewport — outside this section card.
 * - Loading toast uses the documented manual-dismiss pattern with
 *   `toast.dismiss(id)` after a timeout.
 */
export function FeedbackSection() {
  const toast = useToast()

  return (
    <div className="space-y-12">
      {/* === Toast === */}
      <SubSection
        title="Toast notifications"
        description="Появляются в нижнем правом углу. Auto-dismiss 4-5 сек, кроме loading."
        columns={2}
      >
        <Demo title="Триггеры (6 вариантов)" full>
          <Button
            variant="secondary"
            onClick={() => toast.toast("Сохранено", { variant: "success" })}
          >
            Success
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.toast("Ошибка отправки", {
                variant: "danger",
                description: "WB API: 503 Service Unavailable",
              })
            }
          >
            Danger
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.toast("Внимание", {
                variant: "warning",
                description: "12 SKU имеют остаток меньше 20 штук.",
              })
            }
          >
            Warning
          </Button>
          <Button
            variant="secondary"
            onClick={() =>
              toast.toast("Синхронизация", {
                variant: "info",
                description: "Получены данные за последний час.",
              })
            }
          >
            Info
          </Button>
          <Button
            variant="secondary"
            onClick={() => toast.toast("Уведомление", { variant: "default" })}
          >
            Default
          </Button>
          <Button
            variant="secondary"
            onClick={() => {
              const id = toast.loading("Загружаем фото…", {
                description: "Закроется автоматически через 3 сек.",
              })
              window.setTimeout(() => toast.dismiss(id), 3000)
            }}
          >
            Loading
          </Button>
        </Demo>
      </SubSection>

      {/* === Alert === */}
      <SubSection title="Inline alerts" description="Внутри карточек, для контекстных сообщений." columns={2}>
        <Demo title="Info">
          <Alert
            variant="info"
            title="Подсказка"
            description="Заполненность модели влияет на возможность публикации на маркетплейсах."
          />
        </Demo>

        <Demo title="Success">
          <Alert
            variant="success"
            title="Опубликовано"
            description="Модель Vuki синхронизирована с WB и Ozon."
          />
        </Demo>

        <Demo title="Warning">
          <Alert
            variant="warning"
            title="Низкие остатки"
            description="12 SKU имеют остаток меньше 20 штук."
          />
        </Demo>

        <Demo title="Danger">
          <Alert
            variant="danger"
            title="Ошибка валидации"
            description="Цена розничная не может быть меньше себестоимости."
          />
        </Demo>
      </SubSection>

      {/* === Empty states === */}
      <SubSection title="Empty states" columns={2}>
        <Demo title="Пустой список (default Inbox)" full padded={false}>
          <div className="w-full">
            <EmptyState
              title="Нет уведомлений"
              description="Когда что-то изменится в каталоге или появится новая задача — увидишь здесь."
              action={
                <Button size="sm" variant="secondary">
                  Настроить
                </Button>
              }
            />
          </div>
        </Demo>

        <Demo title="Не нашли результаты (кастомная иконка)" full padded={false}>
          <div className="w-full">
            <EmptyState
              icon={<Search className="w-8 h-8" />}
              title="Ничего не найдено"
              description="Попробуй другой запрос или сбрось фильтры."
              action={
                <Button size="sm" variant="ghost">
                  Сбросить
                </Button>
              }
            />
          </div>
        </Demo>

        <Demo title="Без действия" full padded={false}>
          <div className="w-full">
            <EmptyState
              icon={<Box className="w-8 h-8" />}
              title="Пока пусто"
              description="Здесь появятся последние действия команды."
            />
          </div>
        </Demo>
      </SubSection>

      {/* === Loading states === */}
      <SubSection title="Loading states" description="Скелетоны для list/grid карточек.">
        <Demo title="Skeleton card" full>
          <div className="w-full space-y-3">
            <div className="rounded-lg p-4 bg-elevated border border-default">
              <div className="flex items-center gap-3 mb-3">
                <Skeleton className="w-10 h-10 rounded-full" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-3 w-32" />
                  <Skeleton className="h-2.5 w-20" />
                </div>
              </div>
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-3/4 mt-2" />
            </div>

            <div className="rounded-lg p-4 bg-elevated border border-default">
              <Skeleton className="h-4 w-48 mb-2" />
              <Skeleton className="h-3 w-64 mb-1" />
              <Skeleton className="h-3 w-56" />
            </div>
          </div>
        </Demo>
      </SubSection>
    </div>
  )
}
