// Frontend mirror of the backend status map (packages/scheduling/services/appointments.py).
// Linear flow + correction: active states may advance and may always move to
// no_show/cancelled. Terminal states have no outgoing transition (cannot reopen).

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

const STATUS_TRANSITIONS: Record<string, string[]> = {
  pending: ["confirmed", "arrived", "in_progress", "completed", "no_show", "cancelled"],
  confirmed: ["arrived", "in_progress", "completed", "no_show", "cancelled"],
  arrived: ["in_progress", "completed", "no_show", "cancelled"],
  in_progress: ["completed", "cancelled"],
  // terminals (completed, no_show, cancelled, rescheduled) → no transitions
}

/** Allowed target statuses from the given current status (empty for terminal states). */
export function allowedTransitions(status: string): string[] {
  return STATUS_TRANSITIONS[status] ?? []
}
