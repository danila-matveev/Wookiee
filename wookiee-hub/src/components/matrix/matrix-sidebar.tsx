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
  { id: "products", label: "Товары/SKU", icon: ShoppingCart },
  { id: "cards-wb", label: "Склейки WB", icon: CreditCard },
  { id: "cards-ozon", label: "Склейки Ozon", icon: CreditCard },
  { id: "certs", label: "Сертификаты", icon: FileCheck },
]

export function MatrixSidebar() {
  const activeEntity = useMatrixStore((s) => s.activeEntity)
  const setActiveEntity = useMatrixStore((s) => s.setActiveEntity)

  return (
    <aside className="w-56 shrink-0 border-r border-border bg-muted/30 p-3">
      <h3 className="mb-3 px-2 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
        Сущности
      </h3>
      <nav className="space-y-0.5">
        {entities.map((e) => (
          <button
            key={e.id}
            onClick={() => setActiveEntity(e.id)}
            className={cn(
              "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
              activeEntity === e.id
                ? "bg-accent text-accent-foreground font-medium"
                : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
            )}
          >
            <e.icon className="h-4 w-4 shrink-0" />
            {e.label}
          </button>
        ))}
      </nav>
    </aside>
  )
}
