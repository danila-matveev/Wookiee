import { ChevronDown, ChevronRight, FileUp, Plus, Trash2, X } from "lucide-react"
import { useCallback, useRef, useState } from "react"
import { Textarea } from "@/components/ui/textarea"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { StoreResponseConfig, TrainingFile, ProductModel } from "@/types/comms-settings"

interface SettingsTabAiLearningProps {
  config: StoreResponseConfig
  onUpdate: (partial: Partial<StoreResponseConfig>) => void
}

const ACCEPTED_TYPES = ".pdf,.docx,.txt,.csv"
const ACCEPTED_MIME = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
  "text/csv",
]

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export function SettingsTabAiLearning({ config, onUpdate }: SettingsTabAiLearningProps) {
  const [newBrand, setNewBrand] = useState("")
  const [isDragging, setIsDragging] = useState(false)
  const [newNomenclatures, setNewNomenclatures] = useState<Record<string, string>>({})
  const [newNotFor, setNewNotFor] = useState<Record<string, string>>({})
  const [expandedModels, setExpandedModels] = useState<Set<string>>(new Set())
  const fileInputRef = useRef<HTMLInputElement>(null)

  const toggleModel = (id: string) => {
    setExpandedModels((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const allExpanded = config.productModels.length > 0 && config.productModels.every((m) => expandedModels.has(m.id))
  const toggleAll = () => {
    if (allExpanded) {
      setExpandedModels(new Set())
    } else {
      setExpandedModels(new Set(config.productModels.map((m) => m.id)))
    }
  }

  const addBrand = () => {
    if (!newBrand.trim()) return
    onUpdate({
      brandDescriptions: [
        ...config.brandDescriptions,
        { name: newBrand.trim(), description: "" },
      ],
    })
    setNewBrand("")
  }

  const removeBrand = (index: number) => {
    onUpdate({
      brandDescriptions: config.brandDescriptions.filter((_, i) => i !== index),
    })
  }

  const updateBrand = (index: number, field: "name" | "description", value: string) => {
    onUpdate({
      brandDescriptions: config.brandDescriptions.map((b, i) =>
        i === index ? { ...b, [field]: value } : b
      ),
    })
  }

  // --- Product models ---
  const addProductModel = () => {
    const newModel: ProductModel = {
      id: `pm-${Date.now()}`,
      name: "",
      nomenclatures: [],
      description: "",
      recommendWith: [],
    }
    onUpdate({ productModels: [...config.productModels, newModel] })
  }

  const removeProductModel = (id: string) => {
    // Also remove references from other models' recommendWith
    const filtered = config.productModels.filter((m) => m.id !== id)
    const cleaned = filtered.map((m) => ({
      ...m,
      recommendWith: m.recommendWith.filter((rId) => rId !== id),
    }))
    onUpdate({ productModels: cleaned })
  }

  const updateProductModel = (id: string, patch: Partial<ProductModel>) => {
    onUpdate({
      productModels: config.productModels.map((m) =>
        m.id === id ? { ...m, ...patch } : m
      ),
    })
  }

  const addNomenclature = (modelId: string) => {
    const value = (newNomenclatures[modelId] || "").trim()
    if (!value) return
    const model = config.productModels.find((m) => m.id === modelId)
    if (!model || model.nomenclatures.includes(value)) return
    updateProductModel(modelId, { nomenclatures: [...model.nomenclatures, value] })
    setNewNomenclatures((prev) => ({ ...prev, [modelId]: "" }))
  }

  const removeNomenclature = (modelId: string, nom: string) => {
    const model = config.productModels.find((m) => m.id === modelId)
    if (!model) return
    updateProductModel(modelId, { nomenclatures: model.nomenclatures.filter((n) => n !== nom) })
  }

  const toggleRecommendWith = (modelId: string, targetId: string) => {
    const model = config.productModels.find((m) => m.id === modelId)
    if (!model) return
    const has = model.recommendWith.includes(targetId)
    updateProductModel(modelId, {
      recommendWith: has
        ? model.recommendWith.filter((id) => id !== targetId)
        : [...model.recommendWith, targetId],
    })
  }

  const addNotFor = (modelId: string) => {
    const value = (newNotFor[modelId] || "").trim()
    if (!value) return
    const model = config.productModels.find((m) => m.id === modelId)
    if (!model) return
    const existing = model.notFor || []
    if (existing.includes(value)) return
    updateProductModel(modelId, { notFor: [...existing, value] })
    setNewNotFor((prev) => ({ ...prev, [modelId]: "" }))
  }

  const removeNotFor = (modelId: string, item: string) => {
    const model = config.productModels.find((m) => m.id === modelId)
    if (!model) return
    updateProductModel(modelId, { notFor: (model.notFor || []).filter((n) => n !== item) })
  }

  // --- Training files ---
  const handleFiles = useCallback(
    (files: FileList | null) => {
      if (!files) return
      const newFiles: TrainingFile[] = []
      for (let i = 0; i < files.length; i++) {
        const file = files[i]!
        if (!ACCEPTED_MIME.includes(file.type)) continue
        const tf: TrainingFile = {
          id: `tf-${Date.now()}-${i}`,
          name: file.name,
          size: file.size,
          uploadedAt: new Date().toISOString(),
          status: "processing",
        }
        newFiles.push(tf)
      }
      if (newFiles.length === 0) return

      const updated = [...config.trainingFiles, ...newFiles]
      onUpdate({ trainingFiles: updated })

      // Simulate processing -> ready after 2s
      setTimeout(() => {
        onUpdate({
          trainingFiles: updated.map((f) =>
            newFiles.some((nf) => nf.id === f.id) && f.status === "processing"
              ? { ...f, status: "ready" }
              : f
          ),
        })
      }, 2000)
    },
    [config.trainingFiles, onUpdate]
  )

  const removeFile = (id: string) => {
    onUpdate({ trainingFiles: config.trainingFiles.filter((f) => f.id !== id) })
  }

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    setIsDragging(false)
    handleFiles(e.dataTransfer.files)
  }

  return (
    <div className="space-y-5">
      <div>
        <h3 className="text-sm font-semibold mb-1">Обучение AI</h3>
        <p className="text-[12px] text-muted-foreground">Контекст магазина для более точных ответов</p>
      </div>

      <div>
        <label className="text-[12px] text-muted-foreground block mb-1">Описание магазина</label>
        <Textarea
          value={config.storeDescription}
          onChange={(e) => onUpdate({ storeDescription: e.target.value })}
          placeholder="Мы — бренд нижнего белья и домашней одежды из натуральных материалов..."
          className="min-h-[100px] text-[13px]"
        />
      </div>

      <div>
        <label className="text-[12px] text-muted-foreground block mb-2">Бренды</label>
        <div className="space-y-2">
          {config.brandDescriptions.map((brand, i) => (
            <div key={i} className="flex gap-2 items-start p-2 rounded-lg border border-border">
              <div className="flex-1 space-y-1">
                <Input
                  value={brand.name}
                  onChange={(e) => updateBrand(i, "name", e.target.value)}
                  placeholder="Название бренда"
                  className="h-7 text-[12px]"
                />
                <Input
                  value={brand.description}
                  onChange={(e) => updateBrand(i, "description", e.target.value)}
                  placeholder="Описание бренда"
                  className="h-7 text-[12px]"
                />
              </div>
              <Button variant="ghost" size="icon-xs" onClick={() => removeBrand(i)}>
                <X size={12} />
              </Button>
            </div>
          ))}
        </div>
        <div className="flex gap-2 mt-2">
          <Input
            value={newBrand}
            onChange={(e) => setNewBrand(e.target.value)}
            placeholder="Новый бренд"
            className="h-7 text-[12px] max-w-[200px]"
            onKeyDown={(e) => e.key === "Enter" && addBrand()}
          />
          <Button variant="outline" size="xs" onClick={addBrand}>
            <Plus size={12} />
            Добавить
          </Button>
        </div>
      </div>

      {/* Product matrix */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="text-[12px] text-muted-foreground">Товарная матрица</label>
          {config.productModels.length > 0 && (
            <button
              type="button"
              onClick={toggleAll}
              className="text-[11px] text-muted-foreground hover:text-foreground transition-colors"
            >
              {allExpanded ? "Свернуть все" : "Развернуть все"}
            </button>
          )}
        </div>
        <div className="space-y-2">
          {config.productModels.map((model) => {
            const isExpanded = expandedModels.has(model.id)
            return (
              <div key={model.id} className="rounded-lg border border-border overflow-hidden">
                {/* Collapsed header — always visible */}
                <div
                  className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/30 transition-colors"
                  onClick={() => toggleModel(model.id)}
                >
                  {isExpanded ? (
                    <ChevronDown size={14} className="text-muted-foreground shrink-0" />
                  ) : (
                    <ChevronRight size={14} className="text-muted-foreground shrink-0" />
                  )}
                  <span className="text-[13px] font-medium truncate">
                    {model.name || "Без названия"}
                  </span>
                  {!isExpanded && model.positioning && (
                    <span className="text-[11px] text-muted-foreground truncate ml-1">
                      — {model.positioning}
                    </span>
                  )}
                  <div className="ml-auto shrink-0">
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      onClick={(e) => {
                        e.stopPropagation()
                        removeProductModel(model.id)
                      }}
                    >
                      <X size={12} />
                    </Button>
                  </div>
                </div>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="px-3 pb-3 space-y-2 border-t border-border pt-2">
                    <Input
                      value={model.name}
                      onChange={(e) => updateProductModel(model.id, { name: e.target.value })}
                      placeholder="Название модели"
                      className="h-7 text-[12px]"
                    />
                    <Textarea
                      value={model.description}
                      onChange={(e) => updateProductModel(model.id, { description: e.target.value })}
                      placeholder="Описание модели"
                      rows={2}
                      className="text-[12px] min-h-0"
                    />

                    {/* Positioning */}
                    <Input
                      value={model.positioning || ""}
                      onChange={(e) => updateProductModel(model.id, { positioning: e.target.value })}
                      placeholder="Позиционирование (напр. «Универсальная база 24/7»)"
                      className="h-7 text-[12px]"
                    />

                    {/* Not for */}
                    <div>
                      <span className="text-[11px] text-muted-foreground">Кому НЕ подойдёт</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {(model.notFor || []).map((item) => (
                          <span
                            key={item}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-red-500/10 text-[11px] text-red-700 dark:text-red-400"
                          >
                            {item}
                            <button
                              type="button"
                              onClick={() => removeNotFor(model.id, item)}
                              className="text-red-400 hover:text-red-600"
                            >
                              <X size={10} />
                            </button>
                          </span>
                        ))}
                        <Input
                          value={newNotFor[model.id] || ""}
                          onChange={(e) =>
                            setNewNotFor((prev) => ({ ...prev, [model.id]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault()
                              addNotFor(model.id)
                            }
                          }}
                          placeholder="напр. нужен пуш-ап → Wendy"
                          className="h-6 w-[220px] text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Nomenclatures */}
                    <div>
                      <span className="text-[11px] text-muted-foreground">Номенклатуры</span>
                      <div className="flex flex-wrap gap-1 mt-1">
                        {model.nomenclatures.map((nom) => (
                          <span
                            key={nom}
                            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-muted text-[11px]"
                          >
                            {nom}
                            <button
                              type="button"
                              onClick={() => removeNomenclature(model.id, nom)}
                              className="text-muted-foreground hover:text-foreground"
                            >
                              <X size={10} />
                            </button>
                          </span>
                        ))}
                        <Input
                          value={newNomenclatures[model.id] || ""}
                          onChange={(e) =>
                            setNewNomenclatures((prev) => ({ ...prev, [model.id]: e.target.value }))
                          }
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault()
                              addNomenclature(model.id)
                            }
                          }}
                          placeholder="Добавить nmId..."
                          className="h-6 w-[130px] text-[11px]"
                        />
                      </div>
                    </div>

                    {/* Recommend with */}
                    {config.productModels.length > 1 && (
                      <div>
                        <span className="text-[11px] text-muted-foreground">Рекомендовать с</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {config.productModels
                            .filter((other) => other.id !== model.id)
                            .map((other) => {
                              const selected = model.recommendWith.includes(other.id)
                              return (
                                <button
                                  key={other.id}
                                  type="button"
                                  onClick={() => toggleRecommendWith(model.id, other.id)}
                                  className={cn(
                                    "inline-flex items-center px-2 py-0.5 rounded-md text-[11px] border transition-colors",
                                    selected
                                      ? "border-primary bg-primary/10 text-primary"
                                      : "border-border text-muted-foreground hover:border-muted-foreground"
                                  )}
                                >
                                  {other.name || "Без названия"}
                                </button>
                              )
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
        <Button variant="outline" size="xs" className="mt-2" onClick={addProductModel}>
          <Plus size={12} />
          Добавить модель
        </Button>
      </div>

      {/* Training files upload */}
      <div>
        <label className="text-[12px] text-muted-foreground block mb-2">Файлы для обучения</label>

        {/* Drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          className={cn(
            "flex flex-col items-center justify-center gap-2 p-6 rounded-lg border-2 border-dashed cursor-pointer transition-colors",
            isDragging
              ? "border-primary bg-primary/5"
              : "border-border hover:border-muted-foreground/50"
          )}
        >
          <FileUp size={20} className="text-muted-foreground" />
          <div className="text-center">
            <p className="text-[13px] font-medium">Перетащите файлы сюда</p>
            <p className="text-[11px] text-muted-foreground">или нажмите для выбора. PDF, DOCX, TXT, CSV</p>
          </div>
        </div>
        <input
          ref={fileInputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          multiple
          className="hidden"
          onChange={(e) => {
            handleFiles(e.target.files)
            e.target.value = ""
          }}
        />

        {/* File list */}
        {config.trainingFiles.length > 0 && (
          <div className="mt-3 space-y-1.5">
            {config.trainingFiles.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-2 p-2 rounded-lg border border-border text-[12px]"
              >
                <div className="flex-1 min-w-0">
                  <p className="font-medium truncate">{file.name}</p>
                  <p className="text-muted-foreground">{formatFileSize(file.size)}</p>
                </div>
                <span
                  className={cn(
                    "shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium",
                    file.status === "ready" && "bg-emerald-500/10 text-emerald-600",
                    file.status === "processing" && "bg-amber-500/10 text-amber-600",
                    file.status === "error" && "bg-red-500/10 text-red-600"
                  )}
                >
                  {file.status === "ready" && "Готов"}
                  {file.status === "processing" && "Обработка..."}
                  {file.status === "error" && "Ошибка"}
                </span>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation()
                    removeFile(file.id)
                  }}
                >
                  <Trash2 size={12} />
                </Button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
