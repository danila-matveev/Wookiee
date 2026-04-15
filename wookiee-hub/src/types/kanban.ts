export interface KanbanColumn {
  id: string
  title: string
  color: string
  order: number
}

export interface KanbanCard {
  id: string
  title: string
  column: string
  priority: "high" | "medium" | "low"
  dueDate: string | null
  assignee: string | null
  description?: string
  tags?: string[]
  fields: Record<string, string>
  stages?: Stage[]
  blocks?: ContentBlock[]
  comments?: Comment[]
  bitrixTasks?: BitrixTask[]
}

export interface Stage {
  name: string
  done: boolean
  active?: boolean
}

export interface ContentBlock {
  type: "text" | "checklist" | "images"
  title: string
  content?: string
  items?: ChecklistItem[]
  count?: number
}

export interface ChecklistItem {
  text: string
  done: boolean
}

export interface Comment {
  author: string
  text: string
  time: string
}

export interface BitrixTask {
  id: string
  title: string
  status: "done" | "in_progress" | "pending"
  assignee: string
}

export interface BoardConfig {
  id: string
  title: string
  columns: KanbanColumn[]
  defaultView: "kanban" | "table" | "list"
}
