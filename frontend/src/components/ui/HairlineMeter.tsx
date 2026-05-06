import type { CSSProperties } from "react";

interface HairlineMeterProps {
  /** Score value, 0–max. Undefined renders an empty rail. */
  score: number | undefined;
  max?: number;
  /** Color override; otherwise picked from score band. */
  color?: string;
  className?: string;
  style?: CSSProperties;
}

function bandColor(score: number): string {
  if (score >= 80) return "var(--color-done-fg)";
  if (score >= 60) return "var(--color-warn-fg)";
  return "var(--color-failed-fg)";
}

export function HairlineMeter({
  score,
  max = 100,
  color,
  className = "",
  style,
}: HairlineMeterProps) {
  const pct =
    score === undefined ? 0 : Math.max(0, Math.min(100, (score / max) * 100));
  const fill = color ?? (score === undefined ? "transparent" : bandColor(score));

  return (
    <div
      role="meter"
      aria-valuenow={score}
      aria-valuemin={0}
      aria-valuemax={max}
      className={className}
      style={{
        width: "100%",
        height: "1px",
        backgroundColor: "var(--color-surface-3)",
        position: "relative",
        overflow: "hidden",
        ...style,
      }}
    >
      <div
        style={{
          position: "absolute",
          left: 0,
          top: 0,
          height: "100%",
          width: `${pct}%`,
          backgroundColor: fill,
          transition: "width 0.6s var(--ease-out), background-color var(--dur-normal)",
        }}
      />
    </div>
  );
}
