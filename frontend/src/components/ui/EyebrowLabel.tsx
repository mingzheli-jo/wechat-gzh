import type { CSSProperties, ElementType, ReactNode } from "react";

interface EyebrowLabelProps {
  children: ReactNode;
  as?: ElementType;
  tone?: "default" | "subtle";
  className?: string;
  style?: CSSProperties;
}

const toneColor: Record<NonNullable<EyebrowLabelProps["tone"]>, string> = {
  default: "var(--color-ink-3)",
  subtle: "var(--color-ink-4)",
};

export function EyebrowLabel({
  children,
  as: Tag = "p",
  tone = "default",
  className = "",
  style,
}: EyebrowLabelProps) {
  return (
    <Tag
      className={className}
      style={{
        margin: 0,
        fontSize: "var(--text-xs)",
        fontWeight: "var(--weight-semi)",
        color: toneColor[tone],
        textTransform: "uppercase",
        letterSpacing: "0.06em",
        lineHeight: "var(--leading-snug)",
        ...style,
      }}
    >
      {children}
    </Tag>
  );
}
