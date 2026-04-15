export interface DashboardMetric {
  label: string
  value: string
  sub: string
  change?: string
  positive?: boolean
  plan?: string
  forecast?: string
}

export interface ChartDataPoint {
  date: string
  orders: number
  deliveries: number
}

export interface ExpenseRow {
  name: string
  amount: number
  share: number
  delta: number
}

export interface ActivityEvent {
  text: string
  time: string
  color: string
}

export interface ShipmentSummary {
  id: string
  items: number
  warehouse: string
  status: string
  statusColor: string
  date: string
}

export interface QuickStatsData {
  balance: {
    value: number
    sub: string
  }
  rating: {
    value: number
    maxValue: number
    buyoutRate: number
  }
}
