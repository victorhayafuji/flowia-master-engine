import { useEffect, useRef, useState, type ReactNode } from "react"
import { MoreHorizontal } from "lucide-react"

export interface RowMenuItem {
  label: string
  icon?: ReactNode
  onClick: () => void
  destructive?: boolean
  disabled?: boolean
  testId?: string
}

/** Minimal brutal "⋯" overflow menu — closes on outside click and Escape. */
export function RowMenu({ items, label = "Ações" }: { items: RowMenuItem[]; label?: string }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointerDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(false)
    }
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false)
    }
    document.addEventListener("mousedown", onPointerDown)
    document.addEventListener("keydown", onKeyDown)
    return () => {
      document.removeEventListener("mousedown", onPointerDown)
      document.removeEventListener("keydown", onKeyDown)
    }
  }, [open])

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-center w-10 h-10 border-2 border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--accent)] transition-colors"
        data-testid="row-menu-trigger"
      >
        <MoreHorizontal className="w-5 h-5" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 top-full mt-1 z-30 min-w-44 bg-[var(--background)] border-2 border-[var(--border)] shadow-[4px_4px_0px_0px_var(--border)]"
        >
          {items.map((item) => (
            <button
              key={item.label}
              type="button"
              role="menuitem"
              disabled={item.disabled}
              data-testid={item.testId}
              onClick={() => {
                setOpen(false)
                item.onClick()
              }}
              className={`w-full flex items-center gap-2 px-4 py-2 font-mono text-xs font-bold uppercase tracking-widest text-left transition-colors disabled:opacity-50 ${
                item.destructive
                  ? "text-rose-600 hover:bg-rose-600 hover:text-white"
                  : "hover:bg-[var(--accent)]"
              }`}
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
