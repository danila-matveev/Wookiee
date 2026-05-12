import * as React from "react"
import { cn } from "@/lib/utils"
import { FieldWrap, describedBy } from "./FieldWrap"
import { inputBase, inputError, inputSizeMd } from "./_shared"

export interface TextFieldProps {
  id: string
  label?: React.ReactNode
  hint?: React.ReactNode
  error?: React.ReactNode
  required?: boolean
  labelAddon?: React.ReactNode

  value: string
  onChange: (next: string) => void
  placeholder?: string
  disabled?: boolean
  readOnly?: boolean
  autoFocus?: boolean
  maxLength?: number
  type?: "text" | "email" | "url" | "tel" | "search" | "password"
  name?: string
  autoComplete?: string
  inputClassName?: string
  className?: string

  /** Icon rendered inside the input, on the left */
  prefix?: React.ComponentType<{ className?: string }>
  /** Icon rendered inside the input, on the right */
  suffix?: React.ComponentType<{ className?: string }>

  onBlur?: React.FocusEventHandler<HTMLInputElement>
  onFocus?: React.FocusEventHandler<HTMLInputElement>
  onKeyDown?: React.KeyboardEventHandler<HTMLInputElement>
}

export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
  function TextField(
    {
      id,
      label,
      hint,
      error,
      required,
      labelAddon,
      value,
      onChange,
      placeholder,
      disabled,
      readOnly,
      autoFocus,
      maxLength,
      type = "text",
      name,
      autoComplete,
      inputClassName,
      className,
      prefix: Prefix,
      suffix: Suffix,
      onBlur,
      onFocus,
      onKeyDown,
    },
    ref,
  ) {
    const aria = describedBy(id, hint, error)
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
          {Prefix ? (
            <Prefix
              className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
              aria-hidden
            />
          ) : null}
          <input
            ref={ref}
            id={id}
            name={name}
            type={type}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={disabled}
            readOnly={readOnly}
            required={required}
            autoFocus={autoFocus}
            autoComplete={autoComplete}
            maxLength={maxLength}
            aria-invalid={error ? true : undefined}
            aria-describedby={aria}
            onBlur={onBlur}
            onFocus={onFocus}
            onKeyDown={onKeyDown}
            className={cn(
              inputBase,
              inputSizeMd,
              Prefix && "pl-8",
              Suffix && "pr-8",
              error && inputError,
              inputClassName,
            )}
          />
          {Suffix ? (
            <Suffix
              className="w-3.5 h-3.5 absolute right-2.5 top-1/2 -translate-y-1/2 text-muted pointer-events-none"
              aria-hidden
            />
          ) : null}
        </div>
      </FieldWrap>
    )
  },
)
