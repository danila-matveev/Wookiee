import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"

interface Props {
  open: boolean
  onOpenChange: (open: boolean) => void
  challenge: string
  onSubmit: (answer: string) => void
  loading?: boolean
  error?: string | null
}

export function DeleteChallengeDialog({
  open,
  onOpenChange,
  challenge,
  onSubmit,
  loading,
  error,
}: Props) {
  const [answer, setAnswer] = useState("")

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (answer.trim()) {
      onSubmit(answer.trim())
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Подтверждение удаления</DialogTitle>
          <DialogDescription>
            Для подтверждения решите пример:
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4">
            <div className="text-center">
              <span className="text-3xl font-mono font-bold tracking-wider">
                {challenge} = ?
              </span>
            </div>
            <Input
              type="number"
              placeholder="Ответ"
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              autoFocus
              className="text-center text-lg"
            />
            {error && (
              <p className="text-sm text-destructive text-center">{error}</p>
            )}
          </div>
          <DialogFooter className="mt-4">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Отмена
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={!answer.trim() || loading}
            >
              {loading ? "Удаление..." : "Удалить"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
