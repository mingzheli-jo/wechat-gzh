import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "success";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  children: ReactNode;
}

const variantStyles: Record<Variant, CSSProperties> = {
  primary: {
    backgroundColor: "var(--color-accent)",
    color: "var(--color-accent-fg)",
    border: "1px solid transparent",
  },
  secondary: {
    backgroundColor: "var(--color-white)",
    color: "var(--color-ink)",
    border: "1px solid var(--color-surface-3)",
  },
  ghost: {
    backgroundColor: "transparent",
    color: "var(--color-ink)",
    border: "1px solid transparent",
  },
  danger: {
    backgroundColor: "var(--color-failed-fg)",
    color: "var(--color-white)",
    border: "1px solid transparent",
  },
  success: {
    backgroundColor: "var(--color-done-fg)",
    color: "var(--color-white)",
    border: "1px solid transparent",
  },
};

const sizeStyles: Record<Size, CSSProperties> = {
  sm: {
    padding: "0 var(--space-3)",
    fontSize: "var(--text-xs)",
    height: "28px",
  },
  md: {
    padding: "0 var(--space-4)",
    fontSize: "var(--text-sm)",
    height: "36px",
  },
  lg: {
    padding: "0 var(--space-5)",
    fontSize: "var(--text-base)",
    height: "44px",
  },
};

const variantHover: Record<Variant, CSSProperties> = {
  primary: { backgroundColor: "var(--color-ink-2)" },
  secondary: {
    backgroundColor: "var(--color-surface-2)",
    borderColor: "var(--color-surface-4)",
  },
  ghost: { backgroundColor: "var(--color-surface-2)" },
  danger: { opacity: 0.9 },
  success: { opacity: 0.9 },
};

export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  disabled,
  className = "",
  children,
  style,
  ...rest
}: ButtonProps) {
  const isDisabled = disabled || loading;

  return (
    <button
      disabled={isDisabled}
      className={`btn-${variant} ${className}`.trim()}
      style={{
        display: "inline-flex",
        alignItems: "center",
        justifyContent: "center",
        gap: "var(--space-2)",
        borderRadius: "var(--radius-md)",
        fontWeight: "var(--weight-medium)",
        cursor: isDisabled ? "not-allowed" : "pointer",
        opacity: isDisabled ? 0.4 : 1,
        userSelect: "none",
        whiteSpace: "nowrap",
        transition: "all var(--dur-fast)",
        ...variantStyles[variant],
        ...sizeStyles[size],
        ...style,
      }}
      onMouseEnter={(e) => {
        if (isDisabled) return;
        Object.assign(e.currentTarget.style, variantHover[variant]);
      }}
      onMouseLeave={(e) => {
        if (isDisabled) return;
        Object.assign(e.currentTarget.style, variantStyles[variant]);
      }}
      {...rest}
    >
      {loading && (
        <span
          aria-hidden="true"
          style={{
            display: "inline-block",
            width: "14px",
            height: "14px",
            borderRadius: "9999px",
            border: "2px solid currentColor",
            borderTopColor: "transparent",
            animation: "spin 0.8s linear infinite",
          }}
        />
      )}
      {children}
    </button>
  );
}
