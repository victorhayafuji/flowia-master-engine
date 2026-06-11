import { useCallback, useEffect, useMemo, useState } from "react"
import { addDays, startOfToday } from "date-fns"
import { api } from "@/shared/lib/api"
import type { Appointment } from "../types"

type OrgHeader = Record<string, string>

export function useAgendaData(user: unknown, orgHeader: OrgHeader) {
  const [appointments, setAppointments] = useState<Appointment[]>([])
  const [loading, setLoading] = useState(true)
  const [options, setOptions] = useState<{
    patients: Array<{ id: string; name: string }>
    professionals: Array<{
      id: string
      name: string
      working_hours?: Record<string, { start?: string; end?: string } | null> | null
    }>
    services: Array<{ id: string; name: string; duration_minutes?: number; professional_ids?: string[] }>
  }>({ patients: [], professionals: [], services: [] })

  const today = useMemo(() => startOfToday(), [])
  const days = useMemo(() => Array.from({ length: 5 }, (_, i) => addDays(today, i)), [today])

  const refreshAgenda = useCallback(async () => {
    const start = days[0].toISOString().split("T")[0]
    const end = days[4].toISOString().split("T")[0]
    const response = await api.get(`/scheduling/calendar?start_date=${start}&end_date=${end}`, orgHeader)
    setAppointments(response.data || [])
  }, [days, orgHeader])

  const loadOptions = useCallback(async () => {
    const [patRes, profRes, servRes] = await Promise.all([
      api.get("/patients/", orgHeader),
      api.get("/organizations/professionals", orgHeader),
      api.get("/organizations/services", orgHeader),
    ])
    setOptions({
      patients: patRes.data || [],
      professionals: profRes.data || [],
      services: servRes.data || [],
    })
  }, [orgHeader])

  useEffect(() => {
    if (!user) return
    const load = async () => {
      try {
        await refreshAgenda()
        // Professionals power the timeline columns and the week-view filter.
        const profRes = await api.get("/organizations/professionals", orgHeader)
        setOptions((prev) => ({ ...prev, professionals: profRes.data || [] }))
      } catch (err) {
        console.error("Erro ao buscar agenda:", err)
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [user, refreshAgenda, orgHeader])

  return {
    appointments,
    setAppointments,
    loading,
    days,
    options,
    setOptions,
    refreshAgenda,
    loadOptions,
  }
}
