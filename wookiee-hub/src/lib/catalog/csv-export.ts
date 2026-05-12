// W7.3 — единая точка экспорта CSV для каталога (matrix / artikuly / tovary).
// Используем papaparse для корректной квотировки + BOM (﻿) для русификации
// в Excel.  Применяется для bulk-export selected и header-export всей таблицы.

import Papa from "papaparse"

interface ExportOptions {
  filename: string
  rows: Array<Record<string, unknown>>
  /**
   * Optional column mapping.  Если задан — экспортируем только указанные ключи
   * с человекочитаемыми label-заголовками.  Если нет — экспортируем все ключи
   * row as-is (порядок задаётся первым row).
   */
  columns?: Array<{ key: string; label: string }>
}

export function downloadCsv({ filename, rows, columns }: ExportOptions): void {
  if (rows.length === 0) return
  const data = columns
    ? rows.map((r) =>
        Object.fromEntries(columns.map((c) => [c.label, r[c.key] ?? ""])),
      )
    : rows
  const csv = Papa.unparse(data, { quotes: true })
  // BOM (﻿) — Excel понимает UTF-8 кириллицу только при наличии BOM.
  const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const a = document.createElement("a")
  a.href = url
  a.download = filename.endsWith(".csv") ? filename : `${filename}.csv`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
