import * as React from "react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface NumberFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: number | null
  onChange: (next: number | null) => void

  min?: number
  max?: number
  step?: number
  placeholder?: string
  disabled?: boolean
  readOnly?: boolean
  autoFocus?: boolean
  name?: string

  /** Suffix label shown inside the input on the right, e.g. "₽", "%", "шт" */
  suffix?: React.ReactNode

  className?: string
  inputClassName?: string

  onBlur?: React.FocusEventHandler<HTMLInputElement>
  onFocus?: React.FocusEventHandler<HTMLInputElement>
}

export const NumberField = React.forwardRef<HTMLInputElement, NumberFieldProps>(
  function NumberField(
    {
      id,
      label,
      hint,
      error,
      required,
      labelAddon,
      value,
      onChange,
      min,
      max,
      step,
      placeholder,
      disabled,
      readOnly,
      autoFocus,
      name,
      suffix,
      className,
      inputClassName,
      onBlur,
      onFocus,
    },
    ref,
  ) {
    const aria = describedBy(id, hint, error)
    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const raw = e.target.value
      if (raw === "") {
        onChange(null)
        return
      }
      const parsed = Number(raw)
      if (Number.isNaN(parsed)) return
      onChange(parsed)
    }
    return (
      <FieldWrap
        id={id}
        label={label}
        hint={hint}
        error={error}
        required={required}
        labelAddon={labelAddon}
        className={className}
      >
        <div className="relative">
          <input
            ref={ref}
            id={id}
            name={name}
            type="number"
            inputMode="decimal"
            value={value ?? ""}
            onChange={handleChange}
            min={min}
            max={max}
            step={step}
            placeholder={placeholder}
            disabled={disabled}
            readOnly={readOnly}
            required={required}
            autoFocus={autoFocus}
            aria-invalid={error ? true : undefined}
            aria-describedby={aria}
            onBlur={onBlur}
            onFocus={onFocus}
            className={cn(
              inputBase,
              inputSizeMd,
              "tabular-nums",
              suffix && "pr-10",
              error && inputError,
              inputClassName,
            )}
          />
          {suffix ? (
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-muted pointer-events-none tabular-nums">
              {suffix}
            </span>
          ) : null}
        </div>
      </FieldWrap>
    )
  },
)
