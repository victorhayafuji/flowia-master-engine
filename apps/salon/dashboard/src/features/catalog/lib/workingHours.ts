import {
  DEFAULT_WORKING_HOURS,
  WEEKDAYS,
  type DayHours,
  type Professional,
  type WeekdayKey,
} from "../types"

export function normalizeWorkingHours(
  raw?: Partial<Record<WeekdayKey, DayHours | null>>,
): Record<WeekdayKey, DayHours | null> {
  const result = { ...DEFAULT_WORKING_HOURS }
  if (!raw) return result
  for (const { key } of WEEKDAYS) {
    if (key in raw) {
      result[key] = raw[key] ?? null
    }
  }
  return result
}

export function summarizeSchedule(professional: Professional): string {
  const hours = normalizeWorkingHours(professional.working_hours)
  const activeDays = WEEKDAYS.filter(({ key }) => hours[key] !== null)
  if (activeDays.length === 0) return "Sem jornada definida"

  const first = hours[activeDays[0].key]!
  const allSame = activeDays.every(({ key }) => {
    const h = hours[key]
    return h && h.start === first.start && h.end === first.end
  })

  let schedule: string
  if (allSame && activeDays.length >= 2) {
    schedule = `${activeDays[0].label}–${activeDays[activeDays.length - 1].label} ${first.start}–${first.end}`
  } else {
    schedule = activeDays
      .map(({ key, label }) => {
        const h = hours[key]!
        return `${label} ${h.start}–${h.end}`
      })
      .join(" · ")
  }

  const buffer = professional.appointment_buffer_minutes ?? 15
  return `${schedule} · buffer ${buffer}min`
}

export function workingHoursForApi(
  hours: Record<WeekdayKey, DayHours | null>,
): Record<string, DayHours> {
  const payload: Record<string, DayHours> = {}
  for (const { key } of WEEKDAYS) {
    if (hours[key]) payload[key] = hours[key]!
  }
  return payload
}
