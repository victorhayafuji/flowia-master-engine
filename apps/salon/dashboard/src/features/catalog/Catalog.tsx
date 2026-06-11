import { useCallback, useEffect, useState } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/PageHeader"
import { Scissors, UserCog, Plus } from "lucide-react"
import { ProfessionalEditModal } from "./components/modals/ProfessionalEditModal"
import { ServiceEditModal } from "./components/modals/ServiceEditModal"
import { summarizeSchedule } from "./lib/workingHours"
import type { DayHours, Professional, Service, ServiceProfessionalLink } from "./types"

interface CreateServicePayload {
  name: string
  duration_minutes: number
  price: number
}

interface CreateProfessionalPayload {
  name: string
  specialty: string
}

export function Catalog() {
  const { user, orgHeader } = useAuth()
  const [services, setServices] = useState<Service[]>([])
  const [professionals, setProfessionals] = useState<Professional[]>([])
  const [serviceProMap, setServiceProMap] = useState<Record<string, string[]>>({})
  const [loading, setLoading] = useState(true)

  const [isServiceModalOpen, setIsServiceModalOpen] = useState(false)
  const [isProfModalOpen, setIsProfModalOpen] = useState(false)
  const [editingProfessional, setEditingProfessional] = useState<Professional | null>(null)
  const [editingService, setEditingService] = useState<Service | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const [newService, setNewService] = useState({ name: "", duration_minutes: 30, price: 0 })
  const [newProf, setNewProf] = useState({ name: "", role: "" })

  const loadServiceProfessionals = useCallback(
    async (serviceList: Service[]) => {
      if (serviceList.length === 0) {
        setServiceProMap({})
        return
      }
      const entries = await Promise.all(
        serviceList.map(async (svc) => {
          try {
            const res = await api.get(`/organizations/services/${svc.id}/professionals`, orgHeader)
            const rows = (res.data || []) as ServiceProfessionalLink[]
            return [svc.id, rows.map((r) => r.professional?.name || r.professional_id)] as const
          } catch {
            return [svc.id, []] as const
          }
        }),
      )
      setServiceProMap(Object.fromEntries(entries))
    },
    [orgHeader],
  )

  const fetchCatalog = useCallback(async () => {
    if (!user) return
    setLoading(true)
    try {
      const [servRes, profRes] = await Promise.all([
        api.get("/organizations/services", orgHeader),
        api.get("/organizations/professionals", orgHeader),
      ])
      const svcList = (servRes.data || []) as Service[]
      const profList = (profRes.data || []) as Professional[]
      setServices(svcList)
      setProfessionals(profList)
      await loadServiceProfessionals(svcList)
    } catch (err) {
      console.error("Erro ao buscar catálogo:", err)
    } finally {
      setLoading(false)
    }
  }, [user, orgHeader, loadServiceProfessionals])

  useEffect(() => {
    void fetchCatalog()
  }, [fetchCatalog])

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newService.name) return
    setSubmitting(true)
    try {
      const payload: CreateServicePayload = {
        name: newService.name,
        duration_minutes: Number(newService.duration_minutes),
        price: Number(newService.price),
      }
      const { data } = await api.post("/organizations/services", payload, orgHeader)
      if (data) {
        const next = [...services, data as Service].sort((a, b) => a.name.localeCompare(b.name))
        setServices(next)
        setServiceProMap((prev) => ({ ...prev, [(data as Service).id]: [] }))
      }
      setIsServiceModalOpen(false)
      setNewService({ name: "", duration_minutes: 30, price: 0 })
    } catch (err: unknown) {
      console.error("Erro ao criar serviço:", err)
      const detail = err instanceof Error ? err.message : JSON.stringify(err)
      alert(`Erro ao salvar serviço. Detalhes: ${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleCreateProf = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newProf.name) return
    setSubmitting(true)
    try {
      const payload: CreateProfessionalPayload = {
        name: newProf.name,
        specialty: newProf.role,
      }
      const { data } = await api.post("/organizations/professionals", payload, orgHeader)
      if (data) setProfessionals((prev) => [...prev, data as Professional].sort((a, b) => a.name.localeCompare(b.name)))
      setIsProfModalOpen(false)
      setNewProf({ name: "", role: "" })
    } catch (err: unknown) {
      console.error("Erro ao criar profissional:", err)
      const detail = err instanceof Error ? err.message : JSON.stringify(err)
      alert(`Erro ao salvar profissional. Detalhes: ${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveProfessional = async (payload: {
    name: string
    specialty: string | null
    appointment_buffer_minutes: number
    working_hours: Record<string, DayHours>
    break_times: { start: string; end: string }[]
  }) => {
    if (!editingProfessional) return
    setSubmitting(true)
    try {
      const res = await api.put(`/organizations/professionals/${editingProfessional.id}`, payload, orgHeader)
      const updated = (res.data || res) as Professional
      setProfessionals((prev) =>
        prev
          .map((p) =>
            p.id === editingProfessional.id
              ? {
                  ...p,
                  ...updated,
                  ...payload,
                  specialty: payload.specialty ?? undefined,
                }
              : p,
          )
          .sort((a, b) => a.name.localeCompare(b.name)),
      )
      setEditingProfessional(null)
    } catch (err: unknown) {
      console.error("Erro ao atualizar profissional:", err)
      alert(err instanceof Error ? err.message : "Erro ao salvar profissional.")
    } finally {
      setSubmitting(false)
    }
  }

  const handleSaveServiceProfessionals = async (professionalIds: string[]) => {
    if (!editingService) return
    setSubmitting(true)
    try {
      await api.put(
        `/organizations/services/${editingService.id}/professionals`,
        { professional_ids: professionalIds },
        orgHeader,
      )
      const names = professionalIds
        .map((id) => professionals.find((p) => p.id === id)?.name)
        .filter(Boolean) as string[]
      setServiceProMap((prev) => ({ ...prev, [editingService.id]: names }))
      setEditingService(null)
    } catch (err: unknown) {
      console.error("Erro ao atualizar elegibilidade:", err)
      alert(err instanceof Error ? err.message : "Erro ao salvar elegibilidade.")
    } finally {
      setSubmitting(false)
    }
  }

  const renderServicePros = (serviceId: string) => {
    const names = serviceProMap[serviceId]
    if (!names || names.length === 0) {
      return (
        <span className="font-mono text-[10px] font-bold uppercase text-[var(--foreground)]/50 border border-dashed border-[var(--border)] px-1">
          Todos os pros
        </span>
      )
    }
    return names.slice(0, 4).map((name) => (
      <span
        key={`${serviceId}-${name}`}
        className="font-mono text-[10px] font-bold uppercase bg-[var(--foreground)] text-[var(--background)] px-1 border border-[var(--border)]"
      >
        {name.split(" ")[0]}
      </span>
    ))
  }

  return (
    <div className="page-shell">
      <PageHeader
        title="Catálogo"
        subtitle="Configurações do salão — horários, buffer e elegibilidade por serviço"
      />

      <div className="grid gap-8 md:grid-cols-2 flex-1 min-h-0">
        <Card className="flex flex-col min-h-0 h-full">
          <CardHeader className="border-b-4 border-[var(--border)] bg-[var(--background)] flex flex-row items-center justify-between py-4">
            <CardTitle className="flex items-center gap-3 text-xl font-black uppercase">
              <Scissors className="w-6 h-6 text-[var(--accent)]" />
              Serviços
            </CardTitle>
            <Button variant="default" size="sm" className="gap-2" onClick={() => setIsServiceModalOpen(true)}>
              <Plus className="w-4 h-4" /> Novo
            </Button>
          </CardHeader>
          <CardContent className="p-0 flex-1 min-h-0 bg-[var(--surface)] panel-scroll">
            {loading ? (
              <div className="animate-pulse h-32 bg-[var(--foreground)]/5 m-6" />
            ) : services.length === 0 ? (
              <div className="p-8 text-center font-mono text-[var(--foreground)]/50">Nenhum serviço cadastrado.</div>
            ) : (
              <div className="flex flex-col">
                {services.map((s, idx) => (
                  <div
                    key={s.id}
                    className={`flex justify-between items-start gap-3 p-4 border-b-2 border-[var(--border)] ${
                      idx % 2 === 0 ? "bg-[var(--surface)]" : "bg-[var(--background)]"
                    } last:border-b-0`}
                  >
                    <div className="min-w-0 flex-1">
                      <h4 className="font-bold text-[var(--foreground)] uppercase">{s.name}</h4>
                      <p className="font-mono text-sm font-bold text-[var(--foreground)]/60 mt-1">{s.duration_minutes} MIN</p>
                      <div className="flex flex-wrap gap-1 mt-2">{renderServicePros(s.id)}</div>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <div className="font-black text-xl text-[var(--accent)] bg-[var(--foreground)] px-3 py-1 text-[var(--background)] border-2 border-[var(--border)] shadow-[3px_3px_0px_0px_var(--border)]">
                        R$ {s.price}
                      </div>
                      <Button variant="outline" size="sm" className="font-mono text-xs" onClick={() => setEditingService(s)}>
                        Profissionais
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card className="flex flex-col min-h-0 h-full">
          <CardHeader className="border-b-4 border-[var(--border)] bg-[var(--background)] flex flex-row items-center justify-between py-4">
            <CardTitle className="flex items-center gap-3 text-xl font-black uppercase">
              <UserCog className="w-6 h-6 text-[var(--accent)]" />
              Profissionais
            </CardTitle>
            <Button variant="default" size="sm" className="gap-2" onClick={() => setIsProfModalOpen(true)}>
              <Plus className="w-4 h-4" /> Novo
            </Button>
          </CardHeader>
          <CardContent className="p-0 flex-1 min-h-0 bg-[var(--surface)] panel-scroll">
            {loading ? (
              <div className="animate-pulse h-32 bg-[var(--foreground)]/5 m-6" />
            ) : professionals.length === 0 ? (
              <div className="p-8 text-center font-mono text-[var(--foreground)]/50">Nenhum profissional cadastrado.</div>
            ) : (
              <div className="flex flex-col">
                {professionals.map((p, idx) => (
                  <div
                    key={p.id}
                    className={`flex items-start gap-4 p-4 border-b-2 border-[var(--border)] ${
                      idx % 2 === 0 ? "bg-[var(--surface)]" : "bg-[var(--background)]"
                    } last:border-b-0`}
                  >
                    <div className="w-12 h-12 border-2 border-[var(--border)] bg-[var(--accent)] flex items-center justify-center text-[var(--background)] font-black text-xl shadow-[3px_3px_0px_0px_var(--border)] shrink-0">
                      {p.name.charAt(0).toUpperCase()}
                    </div>
                    <div className="min-w-0 flex-1">
                      <h4 className="font-bold text-[var(--foreground)] uppercase">{p.name}</h4>
                      <p className="font-mono text-sm font-bold text-[var(--foreground)]/60 mt-1 uppercase">
                        {p.specialty || "Especialista"}
                      </p>
                      <p className="font-mono text-[10px] text-[var(--foreground)]/50 mt-1 leading-snug">
                        {summarizeSchedule(p)}
                      </p>
                    </div>
                    <Button variant="outline" size="sm" className="font-mono text-xs shrink-0" onClick={() => setEditingProfessional(p)}>
                      Editar
                    </Button>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {isServiceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-md p-8 relative">
            <button
              type="button"
              onClick={() => setIsServiceModalOpen(false)}
              className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
            >
              ×
            </button>
            <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">
              Novo Serviço
            </h2>
            <form onSubmit={handleCreateService} className="space-y-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  Nome do Serviço
                </label>
                <input
                  type="text"
                  required
                  value={newService.name}
                  onChange={(e) => setNewService({ ...newService, name: e.target.value })}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: CORTE FEMININO"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                    Duração (Min)
                  </label>
                  <input
                    type="number"
                    required
                    min="15"
                    step="15"
                    value={newService.duration_minutes}
                    onChange={(e) => setNewService({ ...newService, duration_minutes: Number(e.target.value) })}
                    className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
                <div>
                  <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                    Valor (R$)
                  </label>
                  <input
                    type="number"
                    required
                    min="0"
                    step="0.01"
                    value={newService.price}
                    onChange={(e) => setNewService({ ...newService, price: Number(e.target.value) })}
                    className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
              >
                {submitting ? "Salvando..." : "Confirmar Serviço"}
              </button>
            </form>
          </div>
        </div>
      )}

      {isProfModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-md p-8 relative">
            <button
              type="button"
              onClick={() => setIsProfModalOpen(false)}
              className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
            >
              ×
            </button>
            <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">
              Novo Profissional
            </h2>
            <form onSubmit={handleCreateProf} className="space-y-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  Nome Completo
                </label>
                <input
                  type="text"
                  required
                  value={newProf.name}
                  onChange={(e) => setNewProf({ ...newProf, name: e.target.value })}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: MARIA SILVA"
                />
              </div>
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  Especialidade / Cargo
                </label>
                <input
                  type="text"
                  value={newProf.role}
                  onChange={(e) => setNewProf({ ...newProf, role: e.target.value })}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: CABELEIREIRA"
                />
              </div>
              <button
                type="submit"
                disabled={submitting}
                className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
              >
                {submitting ? "Salvando..." : "Confirmar Profissional"}
              </button>
            </form>
          </div>
        </div>
      )}

      {editingProfessional && (
        <ProfessionalEditModal
          professional={editingProfessional}
          submitting={submitting}
          onClose={() => setEditingProfessional(null)}
          onSave={handleSaveProfessional}
        />
      )}

      {editingService && (
        <ServiceEditModal
          service={editingService}
          professionals={professionals}
          orgHeader={orgHeader}
          submitting={submitting}
          onClose={() => setEditingService(null)}
          onSave={handleSaveServiceProfessionals}
        />
      )}
    </div>
  )
}
