export interface DayHours {
  start: string
  end: string
}

export interface BreakTime {
  start: string
  end: string
}

export type WeekdayKey = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun"

export interface Service {
  id: string
  name: string
  duration_minutes: number
  price: number
}

export interface Professional {
  id: string
  name: string
  specialty?: string
  appointment_buffer_minutes?: number
  working_hours?: Partial<Record<WeekdayKey, DayHours | null>>
  break_times?: BreakTime[]
  is_active?: boolean
}

export interface ServiceProfessionalLink {
  professional_id: string
  professional?: { id: string; name: string; specialty?: string; is_active?: boolean }
}

export const WEEKDAYS: { key: WeekdayKey; label: string }[] = [
  { key: "mon", label: "Seg" },
  { key: "tue", label: "Ter" },
  { key: "wed", label: "Qua" },
  { key: "thu", label: "Qui" },
  { key: "fri", label: "Sex" },
  { key: "sat", label: "Sáb" },
  { key: "sun", label: "Dom" },
]

/** Aligned with packages/scheduling/service.py DEFAULT_WORKING_HOURS */
export const DEFAULT_WORKING_HOURS: Record<WeekdayKey, DayHours | null> = {
  mon: { start: "08:00", end: "18:00" },
  tue: { start: "08:00", end: "18:00" },
  wed: { start: "08:00", end: "18:00" },
  thu: { start: "08:00", end: "18:00" },
  fri: { start: "08:00", end: "18:00" },
  sat: null,
  sun: null,
}

export const BUFFER_OPTIONS = [0, 15, 30, 45] as const
