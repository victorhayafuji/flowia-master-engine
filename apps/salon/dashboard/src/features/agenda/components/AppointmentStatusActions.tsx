import { Button } from "@/components/ui/button"
import { ACTION_LABEL, DESTRUCTIVE_STATUSES, allowedTransitions } from "../lib/appointmentStatus"

interface AppointmentStatusActionsProps {
  currentStatus: string
  onSelect: (status: string) => void
  disabled?: boolean
}

/** Brutal action buttons for the allowed status transitions of an appointment. */
export function AppointmentStatusActions({
  currentStatus,
  onSelect,
  disabled = false,
}: AppointmentStatusActionsProps) {
  const targets = allowedTransitions(currentStatus)

  if (targets.length === 0) {
    return (
      <p className="text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/50">
        Status final
      </p>
    )
  }

  return (
    <div className="flex flex-wrap gap-2">
      {targets.map((target) => (
        <Button
          key={target}
          type="button"
          size="sm"
          variant={DESTRUCTIVE_STATUSES.has(target) ? "destructive" : "outline"}
          disabled={disabled}
          onClick={() => onSelect(target)}
          className="min-h-[44px] flex-1"
          data-testid={`status-action-${target}`}
        >
          {ACTION_LABEL[target] ?? target}
        </Button>
      ))}
    </div>
  )
}
