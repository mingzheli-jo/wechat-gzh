import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-[var(--color-accent)] text-[var(--color-accent-fg)] hover:bg-[var(--color-ink-2)] border-transparent",
  secondary:
    "bg-[var(--color-white)] text-[var(--color-ink)] border-[var(--color-surface-3)] hover:border-[var(--color-surface-4)] hover:bg-[var(--color-surface-2)]",
  ghost:
    "bg-transparent text-[var(--color-ink)] border-transparent hover:bg-[var(--color-surface-2)]",
  danger:
    "bg-[var(--color-failed-fg)] text-white border-transparent hover:opacity-90",
  success:
    "bg-[var(--color-done-fg)] text-white border-transparent hover:opacity-90",
};

const sizeStyles: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[var(--text-xs)] h-7",
  md: "px-4 py-2 text-[var(--text-sm)] h-9",
  lg: "px-5 py-2.5 text-[var(--text-base)] h-11",
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  children,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      disabled={isDisabled}
      className={[
        "inline-flex items-center justify-center gap-2 rounded-[var(--radius-md)] border font-medium",
        "transition-all duration-[var(--dur-fast)]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--color-ink)] focus-visible:ring-offset-1",
        "disabled:opacity-40 disabled:cursor-not-allowed",
        "select-none whitespace-nowrap",
        variantStyles[variant],
        sizeStyles[size],
        className,
      ].join(" ")}
      {...rest}
    >
      {loading && (
        <span
          className="inline-block w-3.5 h-3.5 rounded-full border-2 border-current border-t-transparent animate-spin-slow"
          aria-hidden="true"
        />
      )}
      {children}
    </button>
  );
}
