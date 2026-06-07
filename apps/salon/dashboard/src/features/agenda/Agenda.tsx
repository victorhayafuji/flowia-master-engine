import { useAuth } from "@/features/auth/AuthContext"
import { Button } from "@/components/ui/button"
import { AgendaGrid } from "./components/AgendaGrid"
import { AgendaModals } from "./components/AgendaModals"
import { useAgenda } from "./hooks/useAgenda"

export function Agenda() {
  const { user, orgHeader } = useAuth()
  const agenda = useAgenda(user, orgHeader)

  return (
    <div className="page-shell">
      <div className="page-header mb-6 sm:mb-8 flex flex-col md:flex-row md:justify-between md:items-end border-b-4 border-[var(--border)] pb-6">
        <div>
          <h1 className="text-4xl font-black uppercase tracking-tight text-[var(--foreground)]">Agenda Semanal</h1>
          <p className="text-[var(--foreground)]/70 font-mono mt-1 uppercase text-sm font-bold">
            Gestão Visual de Horários - Arraste e Solte
          </p>
        </div>
        <Button variant="default" className="mt-4 md:mt-0" onClick={() => agenda.setIsNewModalOpen(true)}>
          Novo Agendamento
        </Button>
      </div>

      {agenda.loading ? (
        <div className="border-4 border-[var(--border)] bg-[var(--surface)] flex-1 min-h-[240px] flex items-center justify-center">
          <div className="animate-spin rounded-none h-12 w-12 border-4 border-[var(--border)] border-t-[var(--accent)]" />
        </div>
      ) : (
        <div className="flex-1 min-h-0 panel-scroll-both">
          <AgendaGrid
            days={agenda.days}
            appointments={agenda.appointments}
            activeAppt={agenda.activeAppt}
            onDragStart={agenda.handleDragStart}
            onDragEnd={agenda.handleDragEnd}
            onEdit={agenda.openEdit}
          />
        </div>
      )}

      <AgendaModals
        editingAppt={agenda.editingAppt}
        setEditingAppt={agenda.setEditingAppt}
        editTime={agenda.editTime}
        setEditTime={agenda.setEditTime}
        onEditSave={agenda.handleEditSave}
        isNewModalOpen={agenda.isNewModalOpen}
        setIsNewModalOpen={agenda.setIsNewModalOpen}
        submitting={agenda.submitting}
        newApptData={agenda.newApptData}
        setNewApptData={agenda.setNewApptData}
        options={agenda.options}
        quickAdd={agenda.quickAdd}
        setQuickAdd={agenda.setQuickAdd}
        quickData={agenda.quickData}
        setQuickData={agenda.setQuickData}
        onQuickSave={agenda.handleQuickSave}
        onCreateSubmit={agenda.handleCreateSubmit}
      />
    </div>
  )
}
