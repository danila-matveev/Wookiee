export function formatCurrency(value: number, currency = "\u20BD"): string {
  return `${currency} ${value.toLocaleString("ru-RU")}`
}

export function formatNumber(value: number): string {
  return value.toLocaleString("ru-RU")
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}

export function formatDateTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const date = d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short', year: 'numeric' })
  const time = d.toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })
  return `${date}, ${time}`
}
