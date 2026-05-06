import { type ButtonHTMLAttributes, forwardRef } from 'react';
import { cn } from '@/lib/utils';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  loading?: boolean;
}

const variantClass: Record<Variant, string> = {
  primary: 'bg-primary text-white shadow-sm hover:bg-primary-hover',
  secondary: 'bg-card border border-border-strong hover:bg-primary-light',
  ghost: 'bg-transparent hover:bg-primary-light',
  danger: 'text-danger bg-danger/10 hover:bg-danger/20',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', loading, className, children, disabled, ...rest }, ref) => (
    <button
      ref={ref}
      type={rest.type ?? 'button'}
      disabled={loading || disabled}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3.5 py-2 text-sm font-medium',
        'transition-colors duration-200 disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer',
        'min-h-[36px]',
        variantClass[variant],
        className,
      )}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden="true"
          className="size-3 rounded-full border-2 border-current border-t-transparent animate-spin"
        />
      )}
      {children}
    </button>
  ),
);
Button.displayName = 'Button';

export type { ButtonProps };
