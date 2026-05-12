/**
 * Internal shared styles for forms primitives.
 * Not exported from the public index.
 */

/** 32px height control, semantic tokens only. */
export const inputBase =
  "w-full text-sm rounded-md outline-none transition-colors " +
  "bg-surface text-primary border border-default " +
  "placeholder:text-muted " +
  "hover:border-strong " +
  "focus:border-[var(--color-text-primary)] focus:ring-2 focus:ring-[var(--color-ring)]/30 " +
  "disabled:opacity-50 disabled:cursor-not-allowed"

export const inputSizeMd = "h-8 px-2.5 py-1.5"

export const inputError =
  "border-[var(--color-danger)] focus:border-[var(--color-danger)] focus:ring-[var(--color-danger)]/30"

export const inputDisabled = "opacity-50 cursor-not-allowed pointer-events-none"
