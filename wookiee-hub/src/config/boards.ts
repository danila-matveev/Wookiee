import type { BoardConfig } from "@/types/kanban"

export const boardConfigs: Record<string, BoardConfig> = {
  development: {
    id: "development",
    title: "Разработки",
    defaultView: "kanban",
    columns: [
      { id: "idea", title: "Идея", color: "#6366F1", order: 0 },
      { id: "research", title: "Исследование", color: "#F59E0B", order: 1 },
      { id: "design", title: "Дизайн", color: "#3B82F6", order: 2 },
      { id: "sample", title: "Сэмпл", color: "#8B5CF6", order: 3 },
      { id: "test", title: "Тест", color: "#EC4899", order: 4 },
      { id: "launch", title: "Запуск", color: "#10B981", order: 5 },
    ],
  },
  production: {
    id: "production",
    title: "Производство",
    defaultView: "kanban",
    columns: [
      { id: "order", title: "Заказ", color: "#6366F1", order: 0 },
      { id: "payment", title: "Оплата", color: "#F59E0B", order: 1 },
      { id: "manufacturing", title: "Производство", color: "#3B82F6", order: 2 },
      { id: "shipping", title: "Отгрузка", color: "#8B5CF6", order: 3 },
      { id: "transit", title: "В пути", color: "#EC4899", order: 4 },
      { id: "warehouse", title: "На складе", color: "#10B981", order: 5 },
    ],
  },
  shipments: {
    id: "shipments",
    title: "Поставки FBO",
    defaultView: "kanban",
    columns: [
      { id: "plan", title: "План", color: "#6366F1", order: 0 },
      { id: "assembly", title: "Сборка", color: "#F59E0B", order: 1 },
      { id: "delivery", title: "Доставка", color: "#3B82F6", order: 2 },
      { id: "acceptance", title: "Приёмка", color: "#10B981", order: 3 },
    ],
  },
  ideas: {
    id: "ideas",
    title: "Гипотезы и идеи",
    defaultView: "kanban",
    columns: [
      { id: "inbox", title: "Входящие", color: "#6366F1", order: 0 },
      { id: "evaluation", title: "Оценка", color: "#F59E0B", order: 1 },
      { id: "in_progress", title: "В работу", color: "#3B82F6", order: 2 },
      { id: "done", title: "Готово", color: "#10B981", order: 3 },
      { id: "rejected", title: "Отклонено", color: "#EF4444", order: 4 },
    ],
  },
}
