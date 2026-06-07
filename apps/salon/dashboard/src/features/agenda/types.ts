export interface Appointment {
  id: string
  scheduled_at: string
  duration_minutes: number
  status: string
  professional_id?: string
  patient: { name: string; phone: string }
  professional?: { name: string }
  service: { name: string; price: number }
}

export type AgendaView = "week" | "team"

export const AGENDA_HOURS = Array.from({ length: 11 }, (_, i) => i + 8)
export const AGENDA_QUARTERS = [0, 15, 30, 45]

// Team (single-day) view grid geometry.
export const AGENDA_START_HOUR = 8
export const AGENDA_END_HOUR = 18
export const AGENDA_SLOT_MINUTES = 15
export const TEAM_ROW_HEIGHT = 28 // px per slot row
