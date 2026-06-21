import { useCallback, useEffect, useState } from "react"
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

export interface FinancialBucket {
  amount: number
  count: number
}

export interface FinancialPeriod {
  billed: FinancialBucket
  to_bill: FinancialBucket
  loss: FinancialBucket
}

export type FinancialPeriodKey = "day" | "month" | "year"

export type FinancialByPeriod = Record<FinancialPeriodKey, FinancialPeriod>

export interface ProfKpiCounts {
  appointments: number
  clients: number
}

export interface ProfKpiRow {
  professional: { id: string | null; name: string }
  prev: ProfKpiCounts
  current: ProfKpiCounts
  next: ProfKpiCounts
}

export interface ProfessionalKpiData {
  dates: { prev: string; current: string; next: string }
  professionals: ProfKpiRow[]
}

interface OverviewStats {
  patients: number
  totalNoShows: number
  appointmentsToday: number
  upcoming: UpcomingAppt[]
  counts: BoardCounts
  board: BoardItem[]
  agentSummary: AgentSummary
  financial: FinancialByPeriod
  professionalKpi: ProfessionalKpiData
}

export interface AgentSummary {
  handoffsPending: number
  appointmentsWhatsappToday: number
  conversationsThisWeek: number
}

const EMPTY_AGENT: AgentSummary = {
  handoffsPending: 0,
  appointmentsWhatsappToday: 0,
  conversationsThisWeek: 0,
}

const EMPTY_COUNTS: BoardCounts = { total: 0, in_progress: 0, completed: 0, no_show: 0, upcoming: 0 }

export const EMPTY_BUCKET: FinancialBucket = { amount: 0, count: 0 }
export const EMPTY_PERIOD: FinancialPeriod = { billed: EMPTY_BUCKET, to_bill: EMPTY_BUCKET, loss: EMPTY_BUCKET }
const EMPTY_FINANCIAL: FinancialByPeriod = { day: EMPTY_PERIOD, month: EMPTY_PERIOD, year: EMPTY_PERIOD }
const EMPTY_KPI: ProfessionalKpiData = {
  dates: { prev: "", current: "", next: "" },
  professionals: [],
}

export function useOverviewStats(user: unknown, orgHeader: Record<string, string>) {
  const [stats, setStats] = useState<OverviewStats>({
    patients: 0,
    totalNoShows: 0,
    appointmentsToday: 0,
    upcoming: [],
    counts: EMPTY_COUNTS,
    board: [],
    agentSummary: EMPTY_AGENT,
    financial: EMPTY_FINANCIAL,
    professionalKpi: EMPTY_KPI,
  })

  const fetchStats = useCallback(async () => {
    try {
      const statsRes = await api.get("/dashboard/stats", orgHeader)
      const data = statsRes?.data || statsRes
      setStats((prev) => ({
        ...prev,
        patients: data.patients || 0,
        totalNoShows: data.totalNoShows || 0,
        appointmentsToday: data.appointmentsToday || 0,
        upcoming: data.upcoming || [],
      }))
    } catch (err) {
      console.error("Erro ao buscar stats:", err)
    }
  }, [orgHeader])

  const fetchBoard = useCallback(async () => {
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
  }, [orgHeader])

  const fetchAgentSummary = useCallback(async () => {
    try {
      const res = await api.get("/dashboard/agent-summary", orgHeader)
      const data = res?.data || res
      setStats((prev) => ({
        ...prev,
        agentSummary: {
          handoffsPending: data.handoffsPending ?? 0,
          appointmentsWhatsappToday: data.appointmentsWhatsappToday ?? 0,
          conversationsThisWeek: data.conversationsThisWeek ?? 0,
        },
      }))
    } catch (err) {
      console.error("Erro ao buscar resumo do agente:", err)
    }
  }, [orgHeader])

  const fetchFinancial = useCallback(async () => {
    try {
      const res = await api.get("/dashboard/financial", orgHeader)
      const data = res?.data || res
      setStats((prev) => ({ ...prev, financial: { ...EMPTY_FINANCIAL, ...data } }))
    } catch (err) {
      console.error("Erro ao buscar financeiro:", err)
    }
  }, [orgHeader])

  const fetchProfessionalKpi = useCallback(
    async (date?: string) => {
      try {
        const qs = date ? `?date=${date}` : ""
        const res = await api.get(`/dashboard/professional-kpi${qs}`, orgHeader)
        const data = res?.data || res
        setStats((prev) => ({ ...prev, professionalKpi: { ...EMPTY_KPI, ...data } }))
      } catch (err) {
        console.error("Erro ao buscar KPI por profissional:", err)
      }
    },
    [orgHeader],
  )

  useEffect(() => {
    if (!user) return
    fetchStats()
    fetchBoard()
    fetchAgentSummary()
    fetchFinancial()
    fetchProfessionalKpi()
  }, [user, fetchStats, fetchBoard, fetchAgentSummary, fetchFinancial, fetchProfessionalKpi])

  /** Refetch the board + counts after a status change. */
  const refreshBoard = useCallback(async () => {
    await Promise.all([fetchBoard(), fetchStats(), fetchFinancial()])
  }, [fetchBoard, fetchStats, fetchFinancial])

  return { ...stats, refreshBoard, fetchProfessionalKpi }
}
