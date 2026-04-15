export function formatCurrency(value: number, currency = "\u20BD"): string {
  return `${currency} ${value.toLocaleString("ru-RU")}`
}

export function formatNumber(value: number): string {
  return value.toLocaleString("ru-RU")
}

export function formatPercent(value: number, decimals = 1): string {
  return `${value.toFixed(decimals)}%`
}
