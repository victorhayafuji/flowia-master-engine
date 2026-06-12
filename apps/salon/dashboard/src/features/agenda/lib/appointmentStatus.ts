// Frontend mirror of the backend status map (packages/scheduling/services/appointments.py).
// Manual status changes are permissive so staff can correct filling mistakes
// (e.g. undo a wrongly-marked no_show). Any operational status can be set; only
// `pending` (initial) and `rescheduled` (system) are not manual targets.

/** State display names (used in timeline tooltip / badges). */
export const STATUS_LABEL: Record<string, string> = {
  pending: "Pendente",
  confirmed: "Confirmado",
  arrived: "Chegou",
  in_progress: "Em atendimento",
  completed: "Concluído",
  no_show: "Falta",
  cancelled: "Cancelado",
  rescheduled: "Reagendado",
}

/** Action-verb labels for the transition buttons (Concluído/Chegou/Iniciar/Falta/Cancelado). */
export const ACTION_LABEL: Record<string, string> = {
  confirmed: "Confirmar",
  arrived: "Chegou",
  in_progress: "Iniciar",
  completed: "Concluído",
  no_show: "Falta",
  cancelled: "Cancelado",
}

/** Statuses rendered with destructive styling in the UI. */
export const DESTRUCTIVE_STATUSES = new Set(["no_show", "cancelled"])

/** Operational statuses a user can set manually (excludes pending/rescheduled). */
const MANUAL_TARGETS = ["confirmed", "arrived", "in_progress", "completed", "no_show", "cancelled"]

/** Allowed target statuses from the given current status (all manual targets except itself). */
export function allowedTransitions(status: string): string[] {
  return MANUAL_TARGETS.filter((target) => target !== status)
}
