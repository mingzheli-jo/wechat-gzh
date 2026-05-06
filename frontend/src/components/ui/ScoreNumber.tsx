import type { CSSProperties } from "react";

type Size = "sm" | "md" | "lg" | "hero";

interface ScoreNumberProps {
  score: number | undefined;
  size?: Size;
  /** When true, dimmed neutral color regardless of band. */
  muted?: boolean;
  className?: string;
  style?: CSSProperties;
}

const sizeStyles: Record<Size, CSSProperties> = {
  sm: { fontSize: "var(--text-md)", letterSpacing: "-0.01em" },
  md: { fontSize: "var(--text-xl)", letterSpacing: "-0.02em" },
  lg: { fontSize: "var(--text-2xl)", letterSpacing: "-0.03em" },
  hero: { fontSize: "var(--text-3xl)", letterSpacing: "-0.04em" },
};

function bandColor(score: number): string {
  if (score >= 80) return "var(--color-done-fg)";
  if (score >= 60) return "var(--color-warn-fg)";
  return "var(--color-failed-fg)";
}

export function ScoreNumber({
  score,
  size = "md",
  muted = false,
  className = "",
  style,
}: ScoreNumberProps) {
  const isUnknown = score === undefined;
  const color = isUnknown
    ? "var(--color-ink-4)"
    : muted
    ? "var(--color-ink-2)"
    : bandColor(score);

  return (
    <span
      className={className}
      style={{
        fontFamily: "var(--font-mono)",
        fontWeight: "var(--weight-semi)",
        fontVariantNumeric: "tabular-nums",
        color,
        lineHeight: 1,
        display: "inline-block",
        ...sizeStyles[size],
        ...style,
      }}
    >
      {isUnknown ? "—" : score}
    </span>
  );
}
