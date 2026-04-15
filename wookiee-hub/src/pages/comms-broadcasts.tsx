import { useState } from "react"
import { Plus, Radio } from "lucide-react"
import { Button } from "@/components/ui/button"
import { BroadcastList } from "@/components/comms/broadcast-list"
import { BroadcastCreateForm } from "@/components/comms/broadcast-create-form"
import { useBroadcastsStore } from "@/stores/comms-broadcasts"
import type { Broadcast } from "@/types/comms-broadcasts"

export function CommsBroadcastsPage() {
  const [showForm, setShowForm] = useState(false)
  const broadcasts = useBroadcastsStore((s) => s.broadcasts)
  const addBroadcast = useBroadcastsStore((s) => s.addBroadcast)
  const deleteBroadcast = useBroadcastsStore((s) => s.deleteBroadcast)

  function handleSave(broadcast: Broadcast) {
    addBroadcast(broadcast)
    setShowForm(false)
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-[22px] font-bold">Рассылки</h1>
          <p className="text-[13px] text-muted-foreground mt-0.5">
            Рассылки по клиентам через маркетплейсы
          </p>
        </div>
        <Button
          variant={showForm ? "outline" : "default"}
          onClick={() => setShowForm((v) => !v)}
        >
          <Plus className="size-4" data-icon="inline-start" />
          Новая рассылка
        </Button>
      </div>

      {/* Create form */}
      {showForm && (
        <BroadcastCreateForm
          onSave={handleSave}
          onCancel={() => setShowForm(false)}
        />
      )}

      {/* List */}
      <BroadcastList broadcasts={broadcasts} onDelete={deleteBroadcast} />

      {/* Empty state */}
      {broadcasts.length === 0 && !showForm && (
        <div className="flex flex-col items-center justify-center min-h-[400px] py-10">
          <div className="w-[72px] h-[72px] rounded-2xl bg-accent-soft border border-accent-border flex items-center justify-center mb-4">
            <Radio size={32} className="text-accent" />
          </div>
          <h2 className="text-xl font-bold">Нет рассылок</h2>
          <p className="text-sm text-muted-foreground max-w-[380px] text-center leading-relaxed mt-2">
            Создайте первую рассылку, чтобы начать коммуникацию с клиентами
            через маркетплейсы.
          </p>
          <Button className="mt-4" onClick={() => setShowForm(true)}>
            <Plus className="size-4" data-icon="inline-start" />
            Создать рассылку
          </Button>
        </div>
      )}
    </div>
  )
}
