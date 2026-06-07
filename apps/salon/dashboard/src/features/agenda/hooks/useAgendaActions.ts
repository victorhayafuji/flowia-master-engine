import { useState } from "react"
import { format } from "date-fns"
import type { DragEndEvent } from "@dnd-kit/core"
import { api } from "@/shared/lib/api"
import { resolveSlotDatetime } from "../lib/agendaDropTarget"
import type { Appointment } from "../types"
import type { NewApptFormData } from "../components/AgendaModals"

type OrgHeader = Record<string, string>

export function useAgendaDnD(
  orgHeader: OrgHeader,
  setAppointments: React.Dispatch<React.SetStateAction<Appointment[]>>,
) {
  const [activeId, setActiveId] = useState<string | null>(null)

  const handleDragStart = (event: { active: { id: string | number } }) => {
    setActiveId(String(event.active.id))
  }

  const handleDragEnd = async (event: DragEndEvent) => {
    setActiveId(null)
    const { active, over } = event
    if (!over || active.id === over.id) return

    const newDate = resolveSlotDatetime(event)
    if (!newDate) return
    let previous: Appointment[] = []
    setAppointments((prev) => {
      previous = prev
      return prev.map((appt) => (appt.id === active.id ? { ...appt, scheduled_at: newDate } : appt))
    })
    try {
      await api.post(`/scheduling/calendar/${active.id}`, { scheduled_at: newDate }, orgHeader)
    } catch (err) {
      // Revert optimistic move and surface the conflict (e.g. 409 double booking).
      setAppointments(previous)
      const message = err instanceof Error ? err.message : "Erro ao reagendar."
      alert(message)
    }
  }

  return { activeId, handleDragStart, handleDragEnd }
}

export function useAgendaActions(
  orgHeader: OrgHeader,
  _appointments: Appointment[],
  setAppointments: React.Dispatch<React.SetStateAction<Appointment[]>>,
  options: {
    services: Array<{ id: string; name: string; duration_minutes?: number }>
  },
  setOptions: React.Dispatch<
    React.SetStateAction<{
      patients: Array<{ id: string; name: string }>
      professionals: Array<{ id: string; name: string }>
      services: Array<{ id: string; name: string; duration_minutes?: number }>
    }>
  >,
  refreshAgenda: () => Promise<void>,
) {
  const [editingAppt, setEditingAppt] = useState<Appointment | null>(null)
  const [editTime, setEditTime] = useState("")
  const [isNewModalOpen, setIsNewModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [newApptData, setNewApptData] = useState<NewApptFormData>({
    patient_id: "",
    professional_id: "",
    service_id: "",
    date: "",
    time: "",
  })
  const [quickAdd, setQuickAdd] = useState<{
    type: "patient" | "professional" | "service" | null
    loading: boolean
  }>({ type: null, loading: false })
  const [quickData, setQuickData] = useState<Record<string, string>>({})

  const handleQuickSave = async () => {
    if (!quickAdd.type || !quickData.name) return
    setQuickAdd({ ...quickAdd, loading: true })
    try {
      if (quickAdd.type === "service") {
        const payload = {
          name: quickData.name,
          duration_minutes: Number(quickData.duration_minutes || 30),
          price: 0,
        }
        const res = await api.post("/organizations/services", payload, orgHeader)
        const entity = res.data?.data || res.data
        setOptions((prev) => ({
          ...prev,
          services: [...prev.services, entity].sort((a, b) => a.name.localeCompare(b.name)),
        }))
        setNewApptData((prev) => ({ ...prev, service_id: entity.id }))
      } else if (quickAdd.type === "professional") {
        const payload = { name: quickData.name, specialty: "Cabeleireira" }
        const res = await api.post("/organizations/professionals", payload, orgHeader)
        const entity = res.data?.data || res.data
        setOptions((prev) => ({
          ...prev,
          professionals: [...prev.professionals, entity].sort((a, b) => a.name.localeCompare(b.name)),
        }))
        setNewApptData((prev) => ({ ...prev, professional_id: entity.id }))
      } else if (quickAdd.type === "patient") {
        const payload = { name: quickData.name, phone: quickData.phone || "(00) 00000-0000" }
        const res = await api.post("/patients/", payload, orgHeader)
        const entity = res.data?.data || res.data
        setOptions((prev) => ({
          ...prev,
          patients: [...prev.patients, entity].sort((a, b) => a.name.localeCompare(b.name)),
        }))
        setNewApptData((prev) => ({ ...prev, patient_id: entity.id }))
      }
      setQuickAdd({ type: null, loading: false })
      setQuickData({})
    } catch (err) {
      console.error("Erro no quick add:", err)
      alert("Erro ao salvar cadastro rápido.")
      setQuickAdd({ ...quickAdd, loading: false })
    }
  }

  const handleEditSave = async () => {
    if (!editingAppt || !editTime) return
    const currentDate = new Date(editingAppt.scheduled_at)
    const [h, m] = editTime.split(":").map(Number)
    const newDate = new Date(currentDate.getFullYear(), currentDate.getMonth(), currentDate.getDate(), h, m, 0)
    const newDateStr = format(newDate, "yyyy-MM-dd'T'HH:mm:ssXXX")
    setAppointments((prev) =>
      prev.map((a) => (a.id === editingAppt.id ? { ...a, scheduled_at: newDateStr } : a)),
    )
    setEditingAppt(null)
    try {
      await api.post(`/scheduling/calendar/${editingAppt.id}`, { scheduled_at: newDateStr }, orgHeader)
    } catch (err) {
      console.error("Erro ao atualizar data manual:", err)
    }
  }

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (
      !newApptData.patient_id ||
      !newApptData.professional_id ||
      !newApptData.service_id ||
      !newApptData.date ||
      !newApptData.time
    ) {
      return
    }
    setSubmitting(true)
    const [year, month, day] = newApptData.date.split("-")
    const [h, m] = newApptData.time.split(":")
    const scheduledAt = new Date(Number(year), Number(month) - 1, Number(day), Number(h), Number(m), 0)
    const service = options.services.find((s) => s.id === newApptData.service_id)
    const duration_minutes = service?.duration_minutes || 30
    try {
      const payload = {
        patient_id: newApptData.patient_id,
        professional_id: newApptData.professional_id,
        service_id: newApptData.service_id,
        scheduled_at: scheduledAt.toISOString(),
        duration_minutes,
        status: "confirmed",
        source: "dashboard",
      }
      const response = await api.post("/scheduling/", payload, orgHeader)
      if (response.status === "success" || response.status === 200) {
        setIsNewModalOpen(false)
        await refreshAgenda()
        setNewApptData({ patient_id: "", professional_id: "", service_id: "", date: "", time: "" })
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : "Erro ao criar agendamento."
      alert(errorMessage)
    } finally {
      setSubmitting(false)
    }
  }

  const openEdit = (appt: Appointment) => {
    setEditingAppt(appt)
    const d = new Date(appt.scheduled_at)
    setEditTime(`${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}`)
  }

  const handleCalendarUpdate = async (
    appointmentId: string,
    updates: { scheduled_at?: string; duration_minutes?: number },
  ) => {
    let previous: Appointment[] = []
    setAppointments((prev) => {
      previous = prev
      return prev.map((appt) =>
        appt.id === appointmentId
          ? {
              ...appt,
              ...(updates.scheduled_at ? { scheduled_at: updates.scheduled_at } : {}),
              ...(updates.duration_minutes !== undefined
                ? { duration_minutes: updates.duration_minutes }
                : {}),
            }
          : appt,
      )
    })
    try {
      await api.post(`/scheduling/calendar/${appointmentId}`, updates, orgHeader)
    } catch (err) {
      setAppointments(previous)
      const message = err instanceof Error ? err.message : "Erro ao atualizar agendamento."
      alert(message)
      throw err
    }
  }

  const handleCalendarMove = async (appointmentId: string, scheduledAt: string) => {
    await handleCalendarUpdate(appointmentId, { scheduled_at: scheduledAt })
  }

  const handleCalendarResize = async (
    appointmentId: string,
    scheduledAt: string,
    durationMinutes: number,
  ) => {
    await handleCalendarUpdate(appointmentId, {
      scheduled_at: scheduledAt,
      duration_minutes: durationMinutes,
    })
  }

  return {
    editingAppt,
    setEditingAppt,
    editTime,
    setEditTime,
    isNewModalOpen,
    setIsNewModalOpen,
    submitting,
    newApptData,
    setNewApptData,
    quickAdd,
    setQuickAdd,
    quickData,
    setQuickData,
    handleQuickSave,
    handleEditSave,
    handleCreateSubmit,
    openEdit,
    handleCalendarMove,
    handleCalendarResize,
  }
}

export function useAgendaActiveAppt(activeId: string | null, appointments: Appointment[]) {
  return appointments.find((a) => a.id === activeId)
}
