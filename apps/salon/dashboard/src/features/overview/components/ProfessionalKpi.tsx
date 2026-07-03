import { ArrowDown, ArrowRight, ArrowUp, Users } from "lucide-react"
import { GlassCard, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card"
import type { ProfessionalKpiData, ProfKpiCounts, ProfKpiRow } from "../hooks/useOverviewStats"

function ddmm(iso: string): string {
  if (!iso) return ""
  const [, m, d] = iso.split("-")
  return d && m ? `${d}/${m}` : iso
}

function Delta({ current, prev }: { current: number; prev: number }) {
  const diff = current - prev
  if (diff === 0) {
    return (
      <span className="inline-flex items-center text-[var(--muted)]">
        <ArrowRight className="w-3 h-3" />
      </span>
    )
  }
  const up = diff > 0
  return (
    <span
      className={`inline-flex items-center gap-0.5 font-mono text-[10px] font-bold ${
        up ? "text-[var(--success)]" : "text-[var(--danger)]"
      }`}
    >
      {up ? <ArrowUp className="w-3 h-3" /> : <ArrowDown className="w-3 h-3" />}
      {Math.abs(diff)}
    </span>
  )
}

function DayCell({ label, counts, highlight = false }: { label: string; counts: ProfKpiCounts; highlight?: boolean }) {
  return (
    <div
      className={`flex-1 text-center p-2 border-2 ${
        highlight ? "border-[var(--accent)] bg-[var(--surface-glass)]" : "border-[var(--border)] bg-[var(--background)]"
      }`}
    >
      <div className="text-[10px] uppercase font-bold text-[var(--foreground)]/50 tracking-wide truncate">{label}</div>
      <div className="text-xl font-bold leading-tight">{counts.appointments}</div>
      <div className="text-[10px] font-mono text-[var(--foreground)]/60">
        {counts.clients} cliente{counts.clients === 1 ? "" : "s"}
      </div>
    </div>
  )
}

// Column headers ("Anterior"/"Selecionado"/"Próximo") live above the 3-cell row
// instead of prefixed onto each cell's label — frees ~15-20px per cell so the date
// itself ("01/07") doesn't get squeezed at 360-412px widths.
const COLUMN_HEADERS = ["Anterior", "Selecionado", "Próximo"] as const

function ProfessionalRow({ row, dates }: { row: ProfKpiRow; dates: ProfessionalKpiData["dates"] }) {
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        <Users className="w-4 h-4 text-[var(--accent)]" />
        <span className="font-bold uppercase tracking-tight text-sm">{row.professional.name}</span>
        <span className="text-[10px] font-mono text-[var(--foreground)]/50">
          atend. vs anterior
        </span>
        <Delta current={row.current.appointments} prev={row.prev.appointments} />
      </div>
      <div className="flex gap-2 text-center">
        {COLUMN_HEADERS.map((h) => (
          <span
            key={h}
            className="flex-1 text-[9px] uppercase font-bold text-[var(--foreground)]/40 tracking-wide truncate"
          >
            {h}
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <DayCell label={ddmm(dates.prev)} counts={row.prev} />
        <DayCell label={ddmm(dates.current)} counts={row.current} highlight />
        <DayCell label={ddmm(dates.next)} counts={row.next} />
      </div>
    </div>
  )
}

interface ProfessionalKpiProps {
  data: ProfessionalKpiData
  selectedDate: string
  onDateChange: (date: string) => void
}

export function ProfessionalKpi({ data, selectedDate, onDateChange }: ProfessionalKpiProps) {
  return (
    <GlassCard>
      <CardHeader className="flex flex-row items-start justify-between gap-3">
        <div>
          <CardTitle>Clientes por profissional</CardTitle>
          <CardDescription>Atendimentos e clientes únicos — dia selecionado vs anterior vs seguinte.</CardDescription>
        </div>
        <input
          type="date"
          value={selectedDate}
          onChange={(e) => onDateChange(e.target.value)}
          className="bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono text-xs uppercase focus:outline-none focus:border-[var(--accent)]"
          aria-label="Dia de referência"
        />
      </CardHeader>
      <CardContent>
        {data.professionals.length === 0 ? (
          <div className="py-10 text-center text-[var(--muted)] font-mono text-sm">
            Nenhum profissional ativo.
          </div>
        ) : (
          <div className="space-y-5">
            {data.professionals.map((row) => (
              <ProfessionalRow key={row.professional.id || "none"} row={row} dates={data.dates} />
            ))}
          </div>
        )}
      </CardContent>
    </GlassCard>
  )
}
