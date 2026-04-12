export interface ABCItem {
  name: string
  category: "A" | "B" | "C"
  revenue: number
  orders: number
  margin: number
  share: number
}

export interface AnalyticsMetric {
  label: string
  value: string
  sub: string
  change?: string
  positive?: boolean
}

export interface AnalyticsChartPoint {
  date: string
  orders: number
  buyouts: number
  income: number
  expense: number
}
