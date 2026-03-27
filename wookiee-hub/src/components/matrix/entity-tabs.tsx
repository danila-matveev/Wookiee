import { cn } from "@/lib/utils"
import { useMatrixStore, type MatrixEntity } from "@/stores/matrix-store"
import {
  Box, Palette, Factory, Building2, CreditCard,
  ShoppingCart, FileCheck, Layers,
} from "lucide-react"

const entities: { id: MatrixEntity; label: string; icon: typeof Box }[] = [
  { id: "models", label: "Модели", icon: Box },
  { id: "colors", label: "Цвета", icon: Palette },
  { id: "factories", label: "Фабрики", icon: Factory },
  { id: "importers", label: "Импортёры", icon: Building2 },
  { id: "articles", label: "Артикулы", icon: Layers },
  { id: "products", label: "Товары", icon: ShoppingCart },
  { id: "cards-wb", label: "WB", icon: CreditCard },
  { id: "cards-ozon", label: "Ozon", icon: CreditCard },
  { id: "certs", label: "Сертификаты", icon: FileCheck },
]

export function EntityTabs() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)

  return (
    <div className="flex items-center gap-1 overflow-x-auto px-1">
      {entities.map((e) => {
        const Icon = e.icon
        const isActive = activeEntity === e.id
        return (
          <button
            key={e.id}
            onClick={() => setActiveEntity(e.id)}
            className={cn(
              "flex items-center gap-1.5 whitespace-nowrap rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors",
              isActive
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-foreground",
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {e.label}
          </button>
        )
      })}
    </div>
  )
}
