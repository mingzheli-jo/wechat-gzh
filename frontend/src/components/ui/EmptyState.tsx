import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-6 text-center animate-fade-in">
      {icon && (
        <div className="mb-4 text-[var(--color-surface-4)]">{icon}</div>
      )}
      <p className="text-[var(--text-md)] font-[var(--weight-medium)] text-[var(--color-ink-2)]">
        {title}
      </p>
      {description && (
        <p className="mt-1 text-[var(--text-sm)] text-[var(--color-ink-3)] max-w-xs">
          {description}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
