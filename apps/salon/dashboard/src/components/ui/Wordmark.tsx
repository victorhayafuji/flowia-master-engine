import { cn } from "../../lib/utils"

type WordmarkSize = "sm" | "md" | "lg" | "xl"

const sizeMap: Record<WordmarkSize, { name: string; sub: string }> = {
  sm: { name: "text-base", sub: "text-[8px]" },
  md: { name: "text-2xl", sub: "text-[10px]" },
  lg: { name: "text-4xl", sub: "text-xs" },
  xl: { name: "text-6xl sm:text-7xl", sub: "text-sm" },
}

interface WordmarkProps {
  size?: WordmarkSize
  /** Show the "by GAUSSIX" subtitle (reinforces FlowIA = produto da GAUSSIX). */
  showSubtitle?: boolean
  className?: string
}

/**
 * FlowIA wordmark in the GAUSSIX brand language: Michroma display face with the
 * tri-color purple→orange gradient. Mirrors the landing page's Wordmark.
 */
export function Wordmark({ size = "md", showSubtitle = true, className }: WordmarkProps) {
  const s = sizeMap[size]
  return (
    <div className={cn("flex flex-col leading-none", className)}>
      <span
        className={cn("font-display gradient-text tracking-tight", s.name)}
        style={{ fontFamily: "var(--font-display)" }}
      >
        FlowIA
      </span>
      {showSubtitle && (
        <span
          className={cn(
            "font-mono uppercase tracking-[0.35em] text-[var(--muted)] mt-1",
            s.sub
          )}
        >
          by GAUSSIX
        </span>
      )}
    </div>
  )
}
