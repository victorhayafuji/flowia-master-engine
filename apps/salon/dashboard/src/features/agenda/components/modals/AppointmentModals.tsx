import { Button } from "@/components/ui/button"
import { ModalPortal } from "@/components/ui/modal-portal"
import type { Appointment } from "../../types"
import { isServiceEligible } from "../../lib/serviceEligibility"
import { SelectOrQuickAdd } from "./SelectOrQuickAdd"

interface EditAppointmentModalProps {
  editingAppt: Appointment
  editTime: string
  setEditTime: (time: string) => void
  onClose: () => void
  onSave: () => void
}

export function EditAppointmentModal({
  editingAppt,
  editTime,
  setEditTime,
  onClose,
  onSave,
}: EditAppointmentModalProps) {
  return (
    <ModalPortal>
      <div className="fixed inset-0 z-[10000] flex items-center justify-center bg-black/50 backdrop-blur-sm">
        <div className="relative z-[10001] bg-[var(--background)] border-4 border-[var(--border)] p-6 shadow-[8px_8px_0px_0px_var(--border)] w-full max-w-md mx-4">
        <div className="flex justify-between items-center mb-4 border-b-2 border-[var(--border)] pb-2">
          <h2 className="text-xl font-black uppercase tracking-tight">Editar Horário</h2>
          <button onClick={onClose} className="hover:bg-[var(--accent)] hover:text-white p-1 transition-colors">
            ×
          </button>
        </div>
        <div className="space-y-4">
          <div>
            <p className="text-sm font-bold uppercase text-[var(--foreground)]/70 mb-1">Cliente</p>
            <p className="font-mono bg-[var(--surface)] p-2 border-2 border-[var(--border)]">
              {editingAppt.patient?.name || "Sem Nome"}
            </p>
          </div>
          <div>
            <p className="text-sm font-bold uppercase text-[var(--foreground)]/70 mb-1">Novo Horário (HH:MM)</p>
            <input
              type="time"
              value={editTime}
              onChange={(e) => setEditTime(e.target.value)}
              className="w-full font-mono bg-[var(--surface)] p-2 border-2 border-[var(--border)] outline-none focus:ring-2 focus:ring-[var(--accent)]"
            />
          </div>
          <Button onClick={onSave} className="w-full mt-4 font-bold tracking-widest uppercase">
            Salvar Alteração
          </Button>
        </div>
        </div>
      </div>
    </ModalPortal>
  )
}

export type NewApptFormData = {
  patient_id: string
  professional_id: string
  service_id: string
  date: string
  time: string
}

interface NewAppointmentModalProps {
  submitting: boolean
  newApptData: NewApptFormData
  setNewApptData: React.Dispatch<React.SetStateAction<NewApptFormData>>
  options: {
    patients: Array<{ id: string; name: string }>
    professionals: Array<{ id: string; name: string }>
    services: Array<{ id: string; name: string; duration_minutes?: number; professional_ids?: string[] }>
  }
  quickAdd: { type: "patient" | "professional" | "service" | null; loading: boolean }
  setQuickAdd: React.Dispatch<React.SetStateAction<{ type: "patient" | "professional" | "service" | null; loading: boolean }>>
  quickData: Record<string, string>
  setQuickData: React.Dispatch<React.SetStateAction<Record<string, string>>>
  onQuickSave: () => void
  onClose: () => void
  onSubmit: (e: React.FormEvent) => void
}

export function NewAppointmentModal(props: NewAppointmentModalProps) {
  const {
    submitting,
    newApptData,
    setNewApptData,
    options,
    quickAdd,
    setQuickAdd,
    quickData,
    setQuickData,
    onQuickSave,
    onClose,
    onSubmit,
  } = props

  const eligibleServices = options.services.filter((s) =>
    isServiceEligible(s, newApptData.professional_id),
  )

  const handleProfessionalChange = (professionalId: string) => {
    // Drop the selected service if the new professional can't perform it.
    const selected = options.services.find((s) => s.id === newApptData.service_id)
    const keepService = selected ? isServiceEligible(selected, professionalId) : true
    setNewApptData({
      ...newApptData,
      professional_id: professionalId,
      service_id: keepService ? newApptData.service_id : "",
    })
  }

  return (
    <ModalPortal>
      <div className="fixed inset-0 z-[10000] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
        <div className="relative z-[10001] bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-lg p-8 max-h-[90vh] overflow-y-auto">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
        >
          ×
        </button>
        <h2 className="text-2xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">
          Novo Agendamento
        </h2>
        <form onSubmit={onSubmit} className="space-y-4">
          <SelectOrQuickAdd
            label="Cliente"
            type="patient"
            quickAdd={quickAdd}
            setQuickAdd={setQuickAdd}
            quickData={quickData}
            setQuickData={setQuickData}
            onQuickSave={onQuickSave}
            value={newApptData.patient_id}
            onChange={(v) => setNewApptData({ ...newApptData, patient_id: v })}
            options={options.patients}
            showPhone
          />
          <SelectOrQuickAdd
            label="Profissional"
            type="professional"
            quickAdd={quickAdd}
            setQuickAdd={setQuickAdd}
            quickData={quickData}
            setQuickData={setQuickData}
            onQuickSave={onQuickSave}
            value={newApptData.professional_id}
            onChange={handleProfessionalChange}
            options={options.professionals}
          />
          <SelectOrQuickAdd
            label="Serviço"
            type="service"
            quickAdd={quickAdd}
            setQuickAdd={setQuickAdd}
            quickData={quickData}
            setQuickData={setQuickData}
            onQuickSave={onQuickSave}
            value={newApptData.service_id}
            onChange={(v) => setNewApptData({ ...newApptData, service_id: v })}
            options={eligibleServices}
            showDuration
          />
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                Data
              </label>
              <input
                type="date"
                required
                value={newApptData.date}
                onChange={(e) => setNewApptData({ ...newApptData, date: e.target.value })}
                className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
            <div>
              <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                Hora
              </label>
              <input
                type="time"
                required
                value={newApptData.time}
                onChange={(e) => setNewApptData({ ...newApptData, time: e.target.value })}
                className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
              />
            </div>
          </div>
          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
          >
            {submitting ? "Salvando..." : "Confirmar Agendamento"}
          </button>
        </form>
        </div>
      </div>
    </ModalPortal>
  )
}
