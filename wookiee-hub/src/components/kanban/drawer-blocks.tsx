import { Check, Image, ListChecks, MoreHorizontal, Paperclip, Type } from "lucide-react"
import { cn } from "@/lib/utils"
import type { ContentBlock } from "@/types/kanban"

interface DrawerBlocksProps {
  blocks: ContentBlock[]
}

const blockIcon: Record<ContentBlock["type"], React.ReactNode> = {
  text: <Type size={14} />,
  checklist: <ListChecks size={14} />,
  images: <Image size={14} />,
}

function TextBlock({ content }: { content?: string }) {
  if (!content) return null
  return (
    <p className="text-[13px] text-muted-foreground leading-relaxed">{content}</p>
  )
}

function ChecklistBlock({ items }: { items?: { text: string; done: boolean }[] }) {
  if (!items || items.length === 0) return null
  return (
    <div className="flex flex-col gap-2">
      {items.map((item, i) => (
        <div key={i} className="flex items-center gap-2">
          {item.done ? (
            <div className="w-4 h-4 rounded bg-accent flex items-center justify-center shrink-0">
              <Check size={10} className="text-white" />
            </div>
          ) : (
            <div className="w-4 h-4 rounded border-2 border-text-dim shrink-0" />
          )}
          <span
            className={cn(
              "text-[13px]",
              item.done && "line-through text-muted-foreground"
            )}
          >
            {item.text}
          </span>
        </div>
      ))}
    </div>
  )
}

function ImagesBlock({ count }: { count?: number }) {
  const slots = count ?? 4
  return (
    <div className="grid grid-cols-4 gap-2">
      {Array.from({ length: slots }).map((_, i) => (
        <div
          key={i}
          className={cn(
            "aspect-square bg-bg-hover border border-border rounded-lg",
            "flex items-center justify-center text-text-dim"
          )}
        >
          <Image size={18} />
        </div>
      ))}
    </div>
  )
}

function Block({ block }: { block: ContentBlock }) {
  return (
    <div className="bg-card border border-border rounded-[10px] p-4">
      {/* Block header */}
      <div className="flex items-center gap-2 mb-3">
        <span className="text-text-dim">{blockIcon[block.type]}</span>
        <span className="text-[13px] font-semibold flex-1">{block.title}</span>
        <button
          type="button"
          className="text-text-dim hover:text-foreground p-0.5 rounded hover:bg-bg-hover transition-colors"
        >
          <MoreHorizontal size={14} />
        </button>
      </div>

      {/* Block content */}
      {block.type === "text" && <TextBlock content={block.content} />}
      {block.type === "checklist" && <ChecklistBlock items={block.items} />}
      {block.type === "images" && <ImagesBlock count={block.count} />}
    </div>
  )
}

const addBlockOptions = [
  { label: "Текст", icon: <Type size={12} /> },
  { label: "Чеклист", icon: <ListChecks size={12} /> },
  { label: "Фото", icon: <Image size={12} /> },
  { label: "Файл", icon: <Paperclip size={12} /> },
] as const

export function DrawerBlocks({ blocks }: DrawerBlocksProps) {
  return (
    <div className="space-y-4">
      {blocks.map((block, i) => (
        <Block key={i} block={block} />
      ))}

      {/* Add block buttons */}
      <div className="flex flex-wrap gap-2">
        {addBlockOptions.map((opt) => (
          <button
            key={opt.label}
            type="button"
            className={cn(
              "border border-dashed border-border rounded-md px-2.5 py-1.5",
              "flex items-center gap-1.5 text-[12px] text-text-dim",
              "hover:border-accent-border hover:text-accent",
              "transition-colors cursor-pointer"
            )}
          >
            {opt.icon}
            {opt.label}
          </button>
        ))}
      </div>
    </div>
  )
}
