import type { ReactNode } from "react";

type BadgeVariant = "default" | "pending" | "processing" | "done" | "failed" | "warn" | "outline";

interface BadgeProps {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}

const variantStyles: Record<BadgeVariant, string> = {
  default:
    "bg-[var(--color-surface-2)] text-[var(--color-ink-2)] border-[var(--color-surface-3)]",
  pending:
    "bg-[var(--color-pending)] text-[var(--color-pending-fg)] border-transparent",
  processing:
    "bg-[var(--color-processing)] text-[var(--color-processing-fg)] border-transparent",
  done:
    "bg-[var(--color-done)] text-[var(--color-done-fg)] border-transparent",
  failed:
    "bg-[var(--color-failed)] text-[var(--color-failed-fg)] border-transparent",
  warn:
    "bg-[var(--color-warn)] text-[var(--color-warn-fg)] border-transparent",
  outline:
    "bg-transparent text-[var(--color-ink-2)] border-[var(--color-surface-3)]",
};

export function Badge({ variant = "default", children, className = "" }: BadgeProps) {
  return (
    <span
      className={[
        "inline-flex items-center gap-1 rounded-[var(--radius-full)] border px-2 py-0.5",
        "text-[var(--text-xs)] font-medium leading-none",
        "whitespace-nowrap",
        variantStyles[variant],
        className,
      ].join(" ")}
    >
      {children}
    </span>
  );
}
