// TODO(wave-2): replace with real pages.
// Shared stub for catalog routes that exist in routing/sidebar but not yet
// implemented. Wave 2 agents will replace these with full table pages.

interface InDevelopmentProps {
  title: string
  hint?: string
}

export function InDevelopment({ title, hint }: InDevelopmentProps) {
  return (
    <div className="px-6 py-12 max-w-3xl">
      <div className="text-[11px] uppercase tracking-wider text-label mb-1">
        Каталог
      </div>
      <h1 className="font-serif italic text-3xl text-primary mb-2">{title}</h1>
      <div className="rounded-lg border border-dashed border-strong bg-surface p-8 text-center">
        <div className="text-sm text-secondary font-medium">В разработке</div>
        <div className="text-xs text-muted mt-1">
          {hint ?? "Эта страница будет реализована в Wave 2."}
        </div>
      </div>
    </div>
  )
}
