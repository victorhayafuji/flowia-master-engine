import { useMemo, useState } from "react"
import { Plus, Trash2 } from "lucide-react"
import { normalizeWorkingHours, workingHoursForApi } from "../../lib/workingHours"
import {
  BUFFER_OPTIONS,
  WEEKDAYS,
  type BreakTime,
  type DayHours,
  type Professional,
  type WeekdayKey,
} from "../../types"
import { CatalogModalShell } from "./CatalogModalShell"

interface ProfessionalEditModalProps {
  professional: Professional
  submitting: boolean
  onClose: () => void
  onSave: (payload: {
    name: string
    specialty: string | null
    appointment_buffer_minutes: number
    working_hours: Record<string, DayHours>
    break_times: BreakTime[]
  }) => Promise<void>
}

export function ProfessionalEditModal({
  professional,
  submitting,
  onClose,
  onSave,
}: ProfessionalEditModalProps) {
  const [name, setName] = useState(professional.name)
  const [specialty, setSpecialty] = useState(professional.specialty || "")
  const [buffer, setBuffer] = useState(professional.appointment_buffer_minutes ?? 15)
  const [workingHours, setWorkingHours] = useState(() => normalizeWorkingHours(professional.working_hours))
  const [breakTimes, setBreakTimes] = useState<BreakTime[]>(professional.break_times || [])

  const inputClass =
    "w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono text-xs font-bold uppercase focus:outline-none focus:border-[var(--accent)]"

  const toggleDay = (key: WeekdayKey, enabled: boolean) => {
    setWorkingHours((prev) => ({
      ...prev,
      [key]: enabled ? prev[key] || { start: "08:00", end: "18:00" } : null,
    }))
  }

  const updateDayHours = (key: WeekdayKey, field: keyof DayHours, value: string) => {
    setWorkingHours((prev) => {
      const current = prev[key] || { start: "08:00", end: "18:00" }
      return { ...prev, [key]: { ...current, [field]: value } }
    })
  }

  const addBreak = () => {
    setBreakTimes((prev) => [...prev, { start: "12:00", end: "13:00" }])
  }

  const updateBreak = (index: number, field: keyof BreakTime, value: string) => {
    setBreakTimes((prev) => prev.map((row, i) => (i === index ? { ...row, [field]: value } : row)))
  }

  const removeBreak = (index: number) => {
    setBreakTimes((prev) => prev.filter((_, i) => i !== index))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    await onSave({
      name: name.trim(),
      specialty: specialty.trim() || null,
      appointment_buffer_minutes: buffer,
      working_hours: workingHoursForApi(workingHours),
      break_times: breakTimes,
    })
  }

  const activeDayCount = useMemo(
    () => WEEKDAYS.filter(({ key }) => workingHours[key] !== null).length,
    [workingHours],
  )

  return (
    <CatalogModalShell title="Editar Profissional" onClose={onClose} wide>
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="grid gap-4 md:grid-cols-2">
          <div>
            <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
              Nome
            </label>
            <input type="text" required value={name} onChange={(e) => setName(e.target.value)} className={inputClass} />
          </div>
          <div>
            <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
              Especialidade
            </label>
            <input
              type="text"
              value={specialty}
              onChange={(e) => setSpecialty(e.target.value)}
              className={inputClass}
              placeholder="CABELEIREIRA"
            />
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70">
              Jornada semanal ({activeDayCount} dias)
            </p>
          </div>
          <div className="border-2 border-[var(--border)] divide-y-2 divide-[var(--border)]">
            {WEEKDAYS.map(({ key, label }) => {
              const active = workingHours[key] !== null
              return (
                <div
                  key={key}
                  className={`grid grid-cols-[48px_1fr_1fr_1fr] gap-2 items-center p-2 ${
                    active ? "bg-[var(--surface)]" : "bg-[var(--background)] opacity-60"
                  }`}
                >
                  <label className="flex items-center gap-1 font-mono text-xs font-bold uppercase">
                    <input
                      type="checkbox"
                      checked={active}
                      onChange={(e) => toggleDay(key, e.target.checked)}
                      className="accent-[var(--accent)]"
                    />
                    {label}
                  </label>
                  <input
                    type="time"
                    disabled={!active}
                    value={workingHours[key]?.start || "08:00"}
                    onChange={(e) => updateDayHours(key, "start", e.target.value)}
                    className={inputClass}
                  />
                  <input
                    type="time"
                    disabled={!active}
                    value={workingHours[key]?.end || "18:00"}
                    onChange={(e) => updateDayHours(key, "end", e.target.value)}
                    className={inputClass}
                  />
                  <span className="font-mono text-[10px] text-[var(--foreground)]/50 uppercase">
                    {active ? "Ativo" : "Folga"}
                  </span>
                </div>
              )
            })}
          </div>
        </div>

        <div>
          <div className="flex items-center justify-between mb-2">
            <p className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70">
              Intervalos (almoço / pausa)
            </p>
            <button
              type="button"
              onClick={addBreak}
              className="flex items-center gap-1 border-2 border-[var(--border)] px-2 py-1 text-[10px] font-bold uppercase bg-[var(--surface)]"
            >
              <Plus className="w-3 h-3" /> Adicionar
            </button>
          </div>
          {breakTimes.length === 0 ? (
            <p className="font-mono text-xs text-[var(--foreground)]/50">Nenhum intervalo cadastrado.</p>
          ) : (
            <div className="space-y-2">
              {breakTimes.map((row, index) => (
                <div key={index} className="flex items-center gap-2">
                  <input
                    type="time"
                    value={row.start}
                    onChange={(e) => updateBreak(index, "start", e.target.value)}
                    className={inputClass}
                  />
                  <span className="font-mono text-xs font-bold">–</span>
                  <input
                    type="time"
                    value={row.end}
                    onChange={(e) => updateBreak(index, "end", e.target.value)}
                    className={inputClass}
                  />
                  <button
                    type="button"
                    onClick={() => removeBreak(index)}
                    className="p-2 border-2 border-[var(--border)] text-[var(--foreground)]/60 hover:text-[var(--accent)]"
                    aria-label="Remover intervalo"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div>
          <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
            Buffer entre atendimentos (limpeza / preparo)
          </label>
          <select
            value={buffer}
            onChange={(e) => setBuffer(Number(e.target.value))}
            className={inputClass}
          >
            {BUFFER_OPTIONS.map((minutes) => (
              <option key={minutes} value={minutes}>
                {minutes === 0 ? "Sem buffer" : `${minutes} minutos`}
              </option>
            ))}
          </select>
          <p className="mt-1 font-mono text-[10px] text-[var(--foreground)]/50">
            Soma à duração do serviço no motor de disponibilidade.
          </p>
        </div>

        <button
          type="submit"
          disabled={submitting}
          className="w-full flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
        >
          {submitting ? "Salvando..." : "Salvar Profissional"}
        </button>
      </form>
    </CatalogModalShell>
  )
}
