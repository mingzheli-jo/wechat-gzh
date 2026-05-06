import type { CSSProperties } from "react";

interface HairlineRuleProps {
  /** Vertical margin around the rule. Default 0 (callers control spacing). */
  spacing?: number | string;
  /** Override stroke color. */
  color?: string;
  className?: string;
  style?: CSSProperties;
}

export function HairlineRule({
  spacing = 0,
  color = "var(--color-surface-3)",
  className = "",
  style,
}: HairlineRuleProps) {
  return (
    <hr
      className={className}
      style={{
        border: "none",
        height: "1px",
        backgroundColor: color,
        margin: typeof spacing === "number" ? `${spacing}px 0` : `${spacing} 0`,
        ...style,
      }}
    />
  );
}
