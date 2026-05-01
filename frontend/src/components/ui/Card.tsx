import type { HTMLAttributes, ReactNode } from "react";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  children: ReactNode;
  padding?: "none" | "sm" | "md" | "lg";
}

const paddingStyles = {
  none: "",
  sm: "p-4",
  md: "p-5",
  lg: "p-6",
};

export function Card({ children, padding = "md", className = "", ...rest }: CardProps) {
  return (
    <div
      className={[
        "bg-[var(--color-white)] border border-[var(--color-surface-3)] rounded-[var(--radius-lg)]",
        "shadow-[var(--shadow-sm)]",
        paddingStyles[padding],
        className,
      ].join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}

export function CardHeader({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={[
        "flex items-center justify-between gap-4 pb-4 mb-4",
        "border-b border-[var(--color-surface-2)]",
        className,
      ].join(" ")}
    >
      {children}
    </div>
  );
}

export function CardTitle({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <h3
      className={[
        "text-[var(--text-md)] font-[var(--weight-semi)] text-[var(--color-ink)] leading-snug",
        className,
      ].join(" ")}
    >
      {children}
    </h3>
  );
}
