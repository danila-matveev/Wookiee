import { Database } from "lucide-react"
import { EmptyState } from "@/components/ui-v2/feedback"
import { Demo, SubSection } from "../shared"

/**
 * DataSection — placeholder for Wave 3a deps.
 *
 * Canonical reference: `foundation.jsx:1344-1409` (`function DataSection()`).
 * That section relies on StatCard / DataTable / GroupedTable / Pagination /
 * TreeView / BulkActionsBar primitives — none of which exist yet under
 * `@/components/ui-v2/*`. They are scheduled to land in **Wave 3a — Data
 * display deps**, after which this section will be ported 1:1.
 */
export function DataSection() {
  return (
    <div className="space-y-12">
      <SubSection
        title="Data display"
        description="Раздел появится после Wave 3a — необходимые компоненты ещё не созданы."
      >
        <Demo title="Coming soon" full padded={false}>
          <EmptyState
            icon={<Database className="w-10 h-10" />}
            title="Data display — coming in Wave 3a"
            description="Канонический раздел `foundation.jsx:1344-1409` использует примитивы, которые ещё не портированы под ui-v2. После Wave 3a здесь появится полноценный показ всех компонентов работы с данными."
            action={
              <div className="text-left text-xs text-muted space-y-1 max-w-sm mx-auto mt-2">
                <div className="text-[10px] uppercase tracking-wider text-label mb-2">
                  Ожидается в Wave 3a
                </div>
                <div>· StatCard — 4-col KPI ряд</div>
                <div>· DataTable — sticky-header, selection, expandable rows</div>
                <div>· GroupedTable — pivot-style (планирование поставок)</div>
                <div>· Pagination — 1 / 2 / 3 / … / N</div>
                <div>· TreeView — вложенные категории</div>
                <div>· BulkActionsBar — массовые операции над выбранными строками</div>
              </div>
            }
          />
        </Demo>
      </SubSection>
    </div>
  )
}
