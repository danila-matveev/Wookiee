import { create } from "zustand"
import type { KanbanCard } from "@/types/kanban"
import { boardMockData } from "@/data/kanban-mock"

interface KanbanState {
  selectedCard: KanbanCard | null
  boardCards: Record<string, KanbanCard[]>
  openCard: (card: KanbanCard) => void
  closeCard: () => void
  initBoard: (boardId: string) => void
  moveCard: (boardId: string, cardId: string, toColumn: string) => void
}

export const useKanbanStore = create<KanbanState>((set, get) => ({
  selectedCard: null,
  boardCards: {},
  openCard: (card) => set({ selectedCard: card }),
  closeCard: () => set({ selectedCard: null }),
  initBoard: (boardId) => {
    if (!get().boardCards[boardId]) {
      set((state) => ({
        boardCards: {
          ...state.boardCards,
          [boardId]: boardMockData[boardId] || [],
        },
      }))
    }
  },
  moveCard: (boardId, cardId, toColumn) => {
    set((state) => ({
      boardCards: {
        ...state.boardCards,
        [boardId]: (state.boardCards[boardId] || []).map((card) =>
          card.id === cardId ? { ...card, column: toColumn } : card
        ),
      },
    }))
  },
}))
