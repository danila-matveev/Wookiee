import * as React from "react"
import { Check } from "lucide-react"
import { cn } from "@/lib/utils"

export type StepStatus = "pending" | "active" | "done"

export interface Step {
  label: string
  /** Per-item status. Optional — when omitted, Stepper resolves
   *  statuses from the `current` prop on the parent. */
  status?: StepStatus
}

export interface StepperProps extends React.HTMLAttributes<HTMLDivElement> {
  steps: Step[]
  /**
   * Optional explicit current step index — used when `status` field
   * on items is not set. When provided, overrides individual statuses.
   */
  current?: number
}

function resolveStatuses(steps: Step[], current?: number): StepStatus[] {
  if (typeof current === "number") {
    return steps.map((_, i) =>
      i < current ? "done" : i === current ? "active" : "pending",
    )
  }
  return steps.map((s) => s.status ?? "pending")
}

export const Stepper = React.forwardRef<HTMLDivElement, StepperProps>(
  function Stepper({ steps, current, className, ...rest }, ref) {
    const statuses = resolveStatuses(steps, current)

    return (
      <div
        ref={ref}
        role="list"
        aria-label="Steps"
        className={cn("flex items-start w-full", className)}
        {...rest}
      >
        {steps.map((step, i) => {
          const status = statuses[i]
          const done = status === "done"
          const active = status === "active"
          const isLast = i === steps.length - 1
          const nextDone = !isLast && statuses[i + 1] === "done"

          return (
            <React.Fragment key={`${step.label}-${i}`}>
              <div
                role="listitem"
                aria-current={active ? "step" : undefined}
                className="flex flex-col items-center gap-1.5 shrink-0"
              >
                <div
                  className={cn(
                    "w-7 h-7 rounded-full flex items-center justify-center",
                    "text-xs font-medium tabular-nums transition-colors",
                    done &&
                      "bg-[var(--color-text-primary)] text-[var(--color-surface)]",
                    active &&
                      "bg-surface text-primary ring-2 ring-[var(--color-text-primary)]",
                    !done &&
                      !active &&
                      "bg-surface-muted text-muted border border-default",
                  )}
                >
                  {done ? (
                    <Check className="w-3.5 h-3.5" aria-hidden />
                  ) : (
                    i + 1
                  )}
                </div>
                <span
                  className={cn(
                    "text-[11px] text-center max-w-[120px]",
                    active ? "text-primary font-medium" : "text-muted",
                  )}
                >
                  {step.label}
                </span>
              </div>

              {!isLast && (
                <div
                  aria-hidden
                  className={cn(
                    "flex-1 h-px mt-3.5 mx-2 transition-colors",
                    done || nextDone
                      ? "bg-[var(--color-text-primary)]"
                      : "bg-[var(--color-border-default)]",
                  )}
                />
              )}
            </React.Fragment>
          )
        })}
      </div>
    )
  },
)
