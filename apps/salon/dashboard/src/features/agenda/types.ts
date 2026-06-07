export interface Appointment {
  id: string
  scheduled_at: string
  duration_minutes: number
  status: string
  patient: { name: string; phone: string }
  professional: { name: string }
  service: { name: string; price: number }
}

export const AGENDA_HOURS = Array.from({ length: 11 }, (_, i) => i + 8)
export const AGENDA_QUARTERS = [0, 15, 30, 45]
