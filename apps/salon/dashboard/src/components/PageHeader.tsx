import type { ReactNode } from "react"

interface PageHeaderProps {
  title: string
  subtitle?: string
  actions?: ReactNode
}

/** Standard page header — single visual pattern across all dashboard pages. */
export function PageHeader({ title, subtitle, actions }: PageHeaderProps) {
  return (
    <div className="page-header mb-6 sm:mb-8 flex flex-col gap-4 md:flex-row md:justify-between md:items-end border-b-4 border-[var(--border)] pb-6">
      <div>
        <h1 className="text-2xl sm:text-3xl md:text-4xl font-black uppercase tracking-tight text-[var(--foreground)]">
          {title}
        </h1>
        {subtitle && (
          <p className="text-[var(--foreground)]/70 font-mono mt-1 uppercase text-sm font-bold">
            {subtitle}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
