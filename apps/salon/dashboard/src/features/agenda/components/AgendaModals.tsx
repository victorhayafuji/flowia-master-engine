import type { Appointment } from "../types"
import { EditAppointmentModal, NewAppointmentModal, type NewApptFormData } from "./modals/AppointmentModals"

interface AgendaModalsProps {
  editingAppt: Appointment | null
  setEditingAppt: (appt: Appointment | null) => void
  editTime: string
  setEditTime: (time: string) => void
  onEditSave: () => void
  onStatusChange: (appointmentId: string, status: string) => void
  isNewModalOpen: boolean
  setIsNewModalOpen: (open: boolean) => void
  submitting: boolean
  newApptData: NewApptFormData
  setNewApptData: React.Dispatch<React.SetStateAction<NewApptFormData>>
  options: {
    patients: Array<{ id: string; name: string }>
    professionals: Array<{ id: string; name: string }>
    services: Array<{ id: string; name: string; duration_minutes?: number; professional_ids?: string[] }>
  }
  quickAdd: { type: "patient" | "professional" | "service" | null; loading: boolean }
  setQuickAdd: React.Dispatch<React.SetStateAction<AgendaModalsProps["quickAdd"]>>
  quickData: Record<string, string>
  setQuickData: React.Dispatch<React.SetStateAction<Record<string, string>>>
  onQuickSave: () => void
  onCreateSubmit: (e: React.FormEvent) => void
}

export function AgendaModals(props: AgendaModalsProps) {
  const {
    editingAppt,
    setEditingAppt,
    editTime,
    setEditTime,
    onEditSave,
    onStatusChange,
    isNewModalOpen,
    setIsNewModalOpen,
    submitting,
    newApptData,
    setNewApptData,
    options,
    quickAdd,
    setQuickAdd,
    quickData,
    setQuickData,
    onQuickSave,
    onCreateSubmit,
  } = props

  return (
    <>
      {editingAppt && (
        <EditAppointmentModal
          editingAppt={editingAppt}
          editTime={editTime}
          setEditTime={setEditTime}
          onClose={() => setEditingAppt(null)}
          onSave={onEditSave}
          onStatusChange={onStatusChange}
        />
      )}
      {isNewModalOpen && (
        <NewAppointmentModal
          submitting={submitting}
          newApptData={newApptData}
          setNewApptData={setNewApptData}
          options={options}
          quickAdd={quickAdd}
          setQuickAdd={setQuickAdd}
          quickData={quickData}
          setQuickData={setQuickData}
          onQuickSave={onQuickSave}
          onClose={() => setIsNewModalOpen(false)}
          onSubmit={onCreateSubmit}
        />
      )}
    </>
  )
}

export type { NewApptFormData }
