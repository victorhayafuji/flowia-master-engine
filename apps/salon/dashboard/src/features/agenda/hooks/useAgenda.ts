import { useEffect } from "react"
import { useAgendaData } from "./useAgendaData"
import {
  useAgendaActions,
  useAgendaActiveAppt,
  useAgendaDnD,
} from "./useAgendaActions"

type OrgHeader = Record<string, string>

export function useAgenda(user: unknown, orgHeader: OrgHeader) {
  const {
    appointments,
    setAppointments,
    loading,
    days,
    options,
    setOptions,
    refreshAgenda,
    loadOptions,
  } = useAgendaData(user, orgHeader)

  const { activeId, handleDragStart, handleDragEnd } = useAgendaDnD(orgHeader, setAppointments)

  const actions = useAgendaActions(
    orgHeader,
    appointments,
    setAppointments,
    options,
    setOptions,
    refreshAgenda,
  )

  useEffect(() => {
    if (!actions.isNewModalOpen || options.patients.length > 0) return
    loadOptions().catch((err) => console.error("Erro ao buscar opções:", err))
  }, [actions.isNewModalOpen, options.patients.length, loadOptions])

  const activeAppt = useAgendaActiveAppt(activeId, appointments)

  return {
    appointments,
    loading,
    days,
    activeId,
    activeAppt,
    ...actions,
    options,
    handleDragStart,
    handleDragEnd,
  }
}
