import { useState } from "react"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import type { FilterEntry } from "@/stores/matrix-store"
import { useViewsStore } from "@/stores/views-store"

interface SaveViewDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  entity: string
  currentColumns: string[]
  activeFilters: FilterEntry[]
  sort: { field: string; order: "asc" | "desc" } | null
}

export function SaveViewDialog({
  open,
  onOpenChange,
  entity,
  currentColumns,
  activeFilters,
  sort,
}: SaveViewDialogProps) {
  const [name, setName] = useState("")
  const addView = useViewsStore((s) => s.addView)

  function handleSave() {
    const trimmed = name.trim()
    if (!trimmed) return

    addView(entity, trimmed, {
      columns: currentColumns,
      filters: activeFilters,
      sort,
    })

    setName("")
    onOpenChange(false)
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault()
      handleSave()
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <DialogHeader>
          <DialogTitle>Сохранить вид</DialogTitle>
        </DialogHeader>

        <Input
          placeholder="Название вида"
          value={name}
          onChange={(e) => setName(e.target.value)}
          onKeyDown={handleKeyDown}
          autoFocus
        />

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Отмена
          </Button>
          <Button onClick={handleSave} disabled={!name.trim()}>
            Сохранить
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
