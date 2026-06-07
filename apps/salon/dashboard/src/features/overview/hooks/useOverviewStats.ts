import { useEffect, useState } from "react"
import { api } from "@/shared/lib/api"

interface OverviewStats {
  patients: number
  appointmentsToday: number
  upcoming: Array<{
    id: string
    scheduled_at: string
    patient?: { name: string }
    service?: { name: string }
  }>
}

export function useOverviewStats(user: unknown, orgHeader: Record<string, string>) {
  const [stats, setStats] = useState<OverviewStats>({
    patients: 0,
    appointmentsToday: 0,
    upcoming: [],
  })

  useEffect(() => {
    const fetchStats = async () => {
      if (!user) return
      try {
        const statsRes = await api.get("/dashboard/stats", orgHeader)
        if (statsRes) {
          const data = statsRes.data || statsRes
          setStats({
            patients: data.patients || 0,
            appointmentsToday: data.appointmentsToday || 0,
            upcoming: data.upcoming || [],
          })
        }
      } catch (err) {
        console.error("Erro ao buscar stats:", err)
      }
    }
    fetchStats()
  }, [user, orgHeader])

  return stats
}
