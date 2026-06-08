import { useEffect, useState } from "react"
import { api } from "@/shared/lib/api"
import type { Professional, Service, ServiceProfessionalLink } from "../../types"
import { CatalogModalShell } from "./CatalogModalShell"

interface ServiceEditModalProps {
  service: Service
  professionals: Professional[]
  orgHeader: Record<string, string>
  submitting: boolean
  onClose: () => void
  onSave: (professionalIds: string[]) => Promise<void>
}

export function ServiceEditModal({
  service,
  professionals,
  orgHeader,
  submitting,
  onClose,
  onSave,
}: ServiceEditModalProps) {
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [loadingLinks, setLoadingLinks] = useState(true)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      setLoadingLinks(true)
      try {
        const res = await api.get(`/organizations/services/${service.id}/professionals`, orgHeader)
        const rows = (res.data || []) as ServiceProfessionalLink[]
        if (!cancelled) {
          setSelectedIds(rows.map((r) => r.professional_id))
        }
      } catch (err) {
        console.error("Erro ao carregar profissionais do serviço:", err)
        if (!cancelled) setSelectedIds([])
      } finally {
        if (!cancelled) setLoadingLinks(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [service.id, orgHeader])

  const toggleProfessional = (id: string) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    await onSave(selectedIds)
  }

  const inputClass =
    "accent-[var(--accent)] w-4 h-4 border-2 border-[var(--border)]"

  return (
    <CatalogModalShell title="Profissionais do Serviço" onClose={onClose} wide>
      <div className="mb-4 border-2 border-[var(--border)] bg-[var(--surface)] p-3">
        <p className="font-black uppercase">{service.name}</p>
        <p className="font-mono text-xs text-[var(--foreground)]/60 mt-1">
          {service.duration_minutes} min · R$ {service.price}
        </p>
      </div>

      <p className="font-mono text-xs text-[var(--foreground)]/70 mb-4">
        Selecione quem pode executar este serviço. <strong>Lista vazia = todos os profissionais elegíveis</strong>{" "}
        (regra de fallback do motor de agendamento).
      </p>

      {loadingLinks ? (
        <div className="animate-pulse h-24 bg-[var(--foreground)]/5 mb-4" />
      ) : professionals.length === 0 ? (
        <p className="font-mono text-sm text-[var(--foreground)]/50 mb-4">Cadastre profissionais primeiro.</p>
      ) : (
        <form onSubmit={handleSubmit} className="space-y-2 mb-6">
          {professionals.map((pro) => (
            <label
              key={pro.id}
              className="flex items-center gap-3 border-2 border-[var(--border)] p-3 bg-[var(--surface)] cursor-pointer hover:bg-[var(--background)]"
            >
              <input
                type="checkbox"
                className={inputClass}
                checked={selectedIds.includes(pro.id)}
                onChange={() => toggleProfessional(pro.id)}
              />
              <div>
                <span className="font-bold uppercase">{pro.name}</span>
                {pro.specialty ? (
                  <span className="block font-mono text-[10px] text-[var(--foreground)]/60 uppercase">
                    {pro.specialty}
                  </span>
                ) : null}
              </div>
            </label>
          ))}

          <button
            type="submit"
            disabled={submitting}
            className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
          >
            {submitting ? "Salvando..." : "Salvar Elegibilidade"}
          </button>
        </form>
      )}
    </CatalogModalShell>
  )
}
