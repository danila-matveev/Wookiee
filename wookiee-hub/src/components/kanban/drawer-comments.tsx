import { useState } from "react"
import type { Comment } from "@/types/kanban"

interface DrawerCommentsProps {
  comments: Comment[]
}

function CommentItem({ comment }: { comment: Comment }) {
  const initial = comment.author.charAt(0).toUpperCase()

  return (
    <div className="flex gap-3 mb-4">
      {/* Avatar */}
      <div className="w-7 h-7 rounded-full bg-accent-soft flex items-center justify-center text-accent text-[11px] font-semibold shrink-0">
        {initial}
      </div>

      {/* Content */}
      <div className="min-w-0">
        <div className="flex items-baseline gap-2">
          <span className="text-[12px] font-semibold">{comment.author}</span>
          <span className="text-[11px] text-text-dim">{comment.time}</span>
        </div>
        <p className="text-[13px] text-muted-foreground leading-relaxed mt-0.5">
          {comment.text}
        </p>
      </div>
    </div>
  )
}

export function DrawerComments({ comments }: DrawerCommentsProps) {
  const [localComments, setLocalComments] = useState<Comment[]>(comments)
  const [inputValue, setInputValue] = useState("")

  const handleSubmit = () => {
    const text = inputValue.trim()
    if (!text) return

    setLocalComments((prev) => [
      ...prev,
      { author: "Вы", text, time: "Только что" },
    ])
    setInputValue("")
  }

  return (
    <div className="border-t border-border pt-6">
      {/* Header */}
      <h3 className="text-[13px] font-semibold mb-4">
        Комментарии ({localComments.length})
      </h3>

      {/* Comment list */}
      <div>
        {localComments.map((comment, i) => (
          <CommentItem key={i} comment={comment} />
        ))}
      </div>

      {/* Input area */}
      <div className="flex gap-2 mt-2">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleSubmit()
          }}
          placeholder="Написать комментарий..."
          className="flex-1 bg-card border border-border rounded-md px-3 py-2 text-[13px] placeholder:text-text-dim outline-none focus:border-accent transition-colors"
        />
        <button
          type="button"
          onClick={handleSubmit}
          className="bg-accent text-white rounded-md px-3 py-2 text-[13px] font-medium hover:opacity-90 transition-opacity shrink-0"
        >
          Отправить
        </button>
      </div>
    </div>
  )
}
