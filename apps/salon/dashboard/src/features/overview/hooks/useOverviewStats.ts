import { useEffect, useState } from "react"
import { api } from "@/shared/lib/api"

interface UpcomingAppt {
  id: string
  scheduled_at: string
  status?: string
  duration_minutes?: number
  patient?: { name: string }
  professional?: { name: string }
  service?: { name: string }
}

export interface BoardAppointment {
  id: string
  scheduled_at: string
  ends_at?: string | null
  duration_minutes?: number
  status?: string
  patient?: { name: string }
  service?: { name: string }
}

export interface BoardItem {
  professional: { id: string | null; name: string }
  appointments: BoardAppointment[]
}

interface BoardCounts {
  total: number
  in_progress: number
  completed: number
  no_show: number
  upcoming: number
}

interface OverviewStats {
  patients: number
  appointmentsToday: number
  upcoming: UpcomingAppt[]
  counts: BoardCounts
  board: BoardItem[]
}

const EMPTY_COUNTS: BoardCounts = { total: 0, in_progress: 0, completed: 0, no_show: 0, upcoming: 0 }

export function useOverviewStats(user: unknown, orgHeader: Record<string, string>) {
  const [stats, setStats] = useState<OverviewStats>({
    patients: 0,
    appointmentsToday: 0,
    upcoming: [],
    counts: EMPTY_COUNTS,
    board: [],
  })

  useEffect(() => {
    if (!user) return

    const fetchStats = async () => {
      try {
        const statsRes = await api.get("/dashboard/stats", orgHeader)
        const data = statsRes?.data || statsRes
        setStats((prev) => ({
          ...prev,
          patients: data.patients || 0,
          appointmentsToday: data.appointmentsToday || 0,
          upcoming: data.upcoming || [],
        }))
      } catch (err) {
        console.error("Erro ao buscar stats:", err)
      }
    }

    const fetchBoard = async () => {
      try {
        const boardRes = await api.get("/dashboard/today-board", orgHeader)
        const data = boardRes?.data || boardRes
        setStats((prev) => ({
          ...prev,
          counts: { ...EMPTY_COUNTS, ...(data.counts || {}) },
          board: data.board || [],
        }))
      } catch (err) {
        console.error("Erro ao buscar quadro do dia:", err)
      }
    }

    fetchStats()
    fetchBoard()
  }, [user, orgHeader])

  return stats
}
