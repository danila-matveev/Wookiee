import { type DeleteImpact } from "@/lib/matrix-api"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  impact: DeleteImpact | null
  onConfirm: () => void
}

export function DeleteConfirmDialog({ open, onOpenChange, impact, onConfirm }: Props) {
  if (!impact) return null

  const hasChildren = Object.keys(impact.children).length > 0

  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Удалить {impact.entity_name}?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-3">
              <p>{impact.message}</p>
              {hasChildren && (
                <div className="rounded-md bg-amber-50 dark:bg-amber-950/30 p-3 text-sm">
                  <p className="font-medium text-amber-800 dark:text-amber-200 mb-1">
                    Будут затронуты:
                  </p>
                  <ul className="list-disc list-inside text-amber-700 dark:text-amber-300">
                    {Object.entries(impact.children).map(([table, count]) => (
                      <li key={table}>
                        {table}: {count} записей
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <p className="text-xs text-muted-foreground">
                Запись будет перемещена в архив на 30 дней, затем удалена автоматически.
              </p>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Отмена</AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
          >
            Продолжить удаление
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  )
}
