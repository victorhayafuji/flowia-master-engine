/**
 * Service ↔ professional eligibility (M:N service_professionals).
 *
 * A service is eligible for a professional when it has no explicit eligibility
 * (empty `professional_ids` = any professional can perform it) or the
 * professional is in its eligibility list. With no professional selected,
 * every service is shown.
 */
export interface EligibleService {
  professional_ids?: string[]
}

export function isServiceEligible(service: EligibleService, professionalId: string): boolean {
  return (
    !professionalId ||
    !service.professional_ids?.length ||
    service.professional_ids.includes(professionalId)
  )
}
