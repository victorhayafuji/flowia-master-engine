import type { ReactNode } from "react"

interface CatalogModalShellProps {
  title: string
  onClose: () => void
  children: ReactNode
  wide?: boolean
}

export function CatalogModalShell({ title, onClose, children, wide }: CatalogModalShellProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
      <div
        className={`glass-panel rounded-[var(--radius-xl)] w-full ${
          wide ? "max-w-2xl" : "max-w-md"
        } p-8 relative max-h-[90vh] overflow-y-auto`}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-[var(--muted)] hover:text-[var(--foreground)] font-mono text-xl font-bold"
        >
          ×
        </button>
        <h2 className="font-display text-2xl tracking-tight text-[var(--foreground)] mb-6 border-b border-[var(--border)] pb-3" style={{ fontFamily: "var(--font-display)" }}>
          {title}
        </h2>
        {children}
      </div>
    </div>
  )
}
