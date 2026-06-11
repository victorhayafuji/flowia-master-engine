/**
 * Org-level workday detection from professionals' working_hours.
 *
 * A day is workable when at least one professional has hours configured for
 * that weekday. Fail-open: with no professionals or no working_hours data at
 * all, every day is considered workable (never disable based on missing data).
 */
const WEEKDAY_KEYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"] as const

export interface WorkingHoursProfessional {
  working_hours?: Record<string, { start?: string; end?: string } | null> | null
}

export function orgWorksOnDay(professionals: WorkingHoursProfessional[], date: Date): boolean {
  const withHours = professionals.filter(
    (p) => p.working_hours && Object.keys(p.working_hours).length > 0,
  )
  if (withHours.length === 0) return true

  const key = WEEKDAY_KEYS[date.getDay()]
  return withHours.some((p) => {
    const hours = p.working_hours?.[key]
    return !!hours?.start && !!hours?.end
  })
}
