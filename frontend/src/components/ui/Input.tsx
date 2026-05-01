import type { InputHTMLAttributes, TextareaHTMLAttributes, ReactNode } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  hint?: string;
}

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  hint?: string;
}

const fieldBase =
  "w-full rounded-[var(--radius-md)] border px-3 py-2 text-[var(--text-base)] text-[var(--color-ink)] bg-[var(--color-white)] placeholder:text-[var(--color-ink-4)] " +
  "border-[var(--color-surface-3)] " +
  "transition-colors duration-[var(--dur-fast)] " +
  "focus:outline-none focus:border-[var(--color-ink)] focus:ring-1 focus:ring-[var(--color-ink)] " +
  "disabled:bg-[var(--color-surface-2)] disabled:text-[var(--color-ink-3)] disabled:cursor-not-allowed";

const fieldError =
  "border-[var(--color-failed-fg)] focus:border-[var(--color-failed-fg)] focus:ring-[var(--color-failed-fg)]";

function FieldWrapper({
  label,
  error,
  hint,
  htmlFor,
  children,
}: {
  label?: string;
  error?: string;
  hint?: string;
  htmlFor?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label
          htmlFor={htmlFor}
          className="text-[var(--text-sm)] font-medium text-[var(--color-ink-2)]"
        >
          {label}
        </label>
      )}
      {children}
      {error && (
        <p className="text-[var(--text-xs)] text-[var(--color-failed-fg)]">
          {error}
        </p>
      )}
      {!error && hint && (
        <p className="text-[var(--text-xs)] text-[var(--color-ink-3)]">{hint}</p>
      )}
    </div>
  );
}

export function Input({ label, error, hint, id, className = "", ...rest }: InputProps) {
  const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <FieldWrapper label={label} error={error} hint={hint} htmlFor={fieldId}>
      <input
        id={fieldId}
        className={[fieldBase, error ? fieldError : "", className].join(" ")}
        {...rest}
      />
    </FieldWrapper>
  );
}

export function Textarea({
  label,
  error,
  hint,
  id,
  className = "",
  ...rest
}: TextareaProps) {
  const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <FieldWrapper label={label} error={error} hint={hint} htmlFor={fieldId}>
      <textarea
        id={fieldId}
        className={[
          fieldBase,
          "resize-y min-h-[80px] font-[var(--font-mono)] text-[var(--text-sm)]",
          error ? fieldError : "",
          className,
        ].join(" ")}
        {...rest}
      />
    </FieldWrapper>
  );
}

export function Select({
  label,
  error,
  hint,
  id,
  className = "",
  children,
  ...rest
}: InputProps & { children?: ReactNode }) {
  const fieldId = id ?? label?.toLowerCase().replace(/\s+/g, "-");
  return (
    <FieldWrapper label={label} error={error} hint={hint} htmlFor={fieldId}>
      <select
        id={fieldId}
        className={[
          fieldBase,
          "appearance-none cursor-pointer",
          error ? fieldError : "",
          className,
        ].join(" ")}
        {...(rest as React.SelectHTMLAttributes<HTMLSelectElement>)}
      >
        {children}
      </select>
    </FieldWrapper>
  );
}

// Need to import React for the cast above
import React from "react";
