import type { CSSProperties } from "react";

interface ScoreDialProps {
  /** Score 0–max. Undefined renders a ground-only ring with em-dash. */
  score: number | undefined;
  max?: number;
  /** Outer pixel size. Default 96. */
  size?: number;
  /** Stroke thickness in px. Default 1 — true hairline. */
  strokeWidth?: number;
  /** Color override (rail color stays). */
  color?: string;
  className?: string;
  style?: CSSProperties;
}

function bandColor(score: number): string {
  if (score >= 80) return "var(--color-done-fg)";
  if (score >= 60) return "var(--color-warn-fg)";
  return "var(--color-failed-fg)";
}

/**
 * Hairline progress ring with score number centered.
 * Used for the DraftDetail hero score; uses ScoreNumber-equivalent typography
 * inside the SVG via foreignObject-free approach (text node).
 */
export function ScoreDial({
  score,
  max = 100,
  size = 96,
  strokeWidth = 1,
  color,
  className = "",
  style,
}: ScoreDialProps) {
  const isUnknown = score === undefined;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const pct = isUnknown ? 0 : Math.max(0, Math.min(1, score / max));
  const offset = circumference * (1 - pct);
  const fillColor = isUnknown
    ? "transparent"
    : color ?? bandColor(score);

  // 12 o'clock start position via -90deg rotation on the fill circle.
  return (
    <div
      className={className}
      style={{
        position: "relative",
        width: size,
        height: size,
        flexShrink: 0,
        ...style,
      }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        {/* ground ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--color-surface-3)"
          strokeWidth={strokeWidth}
        />
        {/* score fill */}
        {!isUnknown && (
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={fillColor}
            strokeWidth={strokeWidth}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="butt"
            style={{
              transform: "rotate(-90deg)",
              transformOrigin: "50% 50%",
              transition: "stroke-dashoffset 0.6s var(--ease-out), stroke var(--dur-normal)",
            }}
          />
        )}
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--font-sans)",
          fontWeight: "var(--weight-semi)",
          fontVariantNumeric: "tabular-nums",
          fontSize: `${size * 0.4}px`,
          letterSpacing: "-0.04em",
          lineHeight: 1,
          color: isUnknown ? "var(--color-ink-4)" : fillColor,
        }}
      >
        {isUnknown ? "—" : score}
      </div>
    </div>
  );
}
