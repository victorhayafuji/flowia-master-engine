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
        className={`bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full ${
          wide ? "max-w-2xl" : "max-w-md"
        } p-8 relative max-h-[90vh] overflow-y-auto`}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
        >
          ×
        </button>
        <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">
          {title}
        </h2>
        {children}
      </div>
    </div>
  )
}
