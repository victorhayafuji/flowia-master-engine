import { useState, useEffect } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Scissors, UserCog, Plus } from "lucide-react"

interface Service {
  id: string
  name: string
  duration_minutes: number
  price: number
}

interface Professional {
  id: string
  name: string
  role?: string
}

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
  const [loading, setLoading] = useState(true)

  // Modal States
  const [isServiceModalOpen, setIsServiceModalOpen] = useState(false)
  const [isProfModalOpen, setIsProfModalOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  
  const [newService, setNewService] = useState({ name: '', duration_minutes: 30, price: 0 })
  const [newProf, setNewProf] = useState({ name: '', role: '' })

  useEffect(() => {
    const fetchCatalog = async () => {
      if (!user) return

      try {
        const [servRes, profRes] = await Promise.all([
          api.get('/organizations/services', orgHeader),
          api.get('/organizations/professionals', orgHeader)
        ])

        setServices(servRes.data || [])
        setProfessionals(profRes.data || [])
      } catch (err) {
        console.error("Erro ao buscar catálogo:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchCatalog()
  }, [user, orgHeader])

  const handleCreateService = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newService.name) return
    setSubmitting(true)
    try {
      const payload: CreateServicePayload = {
        name: newService.name,
        duration_minutes: Number(newService.duration_minutes),
        price: Number(newService.price)
      }
      
      const { data } = await api.post('/organizations/services', payload, orgHeader)
      
      if (data) setServices(prev => [...prev, data].sort((a,b) => a.name.localeCompare(b.name)))
      setIsServiceModalOpen(false)
      setNewService({ name: '', duration_minutes: 30, price: 0 })
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
        specialty: newProf.role
      }
      
      const { data } = await api.post('/organizations/professionals', payload, orgHeader)
      
      if (data) setProfessionals(prev => [...prev, data].sort((a,b) => a.name.localeCompare(b.name)))
      setIsProfModalOpen(false)
      setNewProf({ name: '', role: '' })
    } catch (err: unknown) {
      console.error("Erro ao criar profissional:", err)
      const detail = err instanceof Error ? err.message : JSON.stringify(err)
      alert(`Erro ao salvar profissional. Detalhes: ${detail}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="page-shell">
      <div className="page-header mb-6 sm:mb-8 border-b-4 border-[var(--border)] pb-6">
        <h1 className="text-4xl font-black uppercase tracking-tight text-[var(--foreground)]">Configurações do Salão</h1>
        <p className="text-[var(--foreground)]/70 font-mono mt-1 uppercase text-sm font-bold">Catálogo de Serviços e Profissionais</p>
      </div>

      <div className="grid gap-8 md:grid-cols-2 flex-1 min-h-0">
        {/* SERVIÇOS */}
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
              <div className="animate-pulse h-32 bg-[var(--foreground)]/5 m-6"></div>
            ) : services.length === 0 ? (
               <div className="p-8 text-center font-mono text-[var(--foreground)]/50">Nenhum serviço cadastrado.</div>
            ) : (
              <div className="flex flex-col">
                {services.map((s, idx) => (
                  <div key={s.id} className={`flex justify-between items-center p-4 border-b-2 border-[var(--border)] ${idx % 2 === 0 ? 'bg-[var(--surface)]' : 'bg-[var(--background)]'} last:border-b-0`}>
                    <div>
                      <h4 className="font-bold text-[var(--foreground)] uppercase">{s.name}</h4>
                      <p className="font-mono text-sm font-bold text-[var(--foreground)]/60 mt-1">{s.duration_minutes} MIN</p>
                    </div>
                    <div className="font-black text-xl text-[var(--accent)] bg-[var(--foreground)] px-3 py-1 text-[var(--background)] border-2 border-[var(--border)] shadow-[3px_3px_0px_0px_var(--border)]">
                      R$ {s.price}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* PROFISSIONAIS */}
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
              <div className="animate-pulse h-32 bg-[var(--foreground)]/5 m-6"></div>
            ) : professionals.length === 0 ? (
               <div className="p-8 text-center font-mono text-[var(--foreground)]/50">Nenhum profissional cadastrado.</div>
            ) : (
              <div className="flex flex-col">
                {professionals.map((p, idx) => (
                  <div key={p.id} className={`flex items-center gap-4 p-4 border-b-2 border-[var(--border)] ${idx % 2 === 0 ? 'bg-[var(--surface)]' : 'bg-[var(--background)]'} last:border-b-0`}>
                    <div className="w-12 h-12 border-2 border-[var(--border)] bg-[var(--accent)] flex items-center justify-center text-[var(--background)] font-black text-xl shadow-[3px_3px_0px_0px_var(--border)] shrink-0">
                      {p.name.charAt(0).toUpperCase()}
                    </div>
                    <div>
                      <h4 className="font-bold text-[var(--foreground)] uppercase">{p.name}</h4>
                      <p className="font-mono text-sm font-bold text-[var(--foreground)]/60 mt-1 uppercase">{p.role || 'Especialista'}</p>
                    </div>
                    <div className="ml-auto">
                      <Button variant="outline" size="sm" className="font-mono text-xs">Editar</Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* SERVICE MODAL */}
      {isServiceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-md p-8 relative">
            <button 
              onClick={() => setIsServiceModalOpen(false)}
              className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
            >
              ×
            </button>
            <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">Novo Serviço</h2>
            
            <form onSubmit={handleCreateService} className="space-y-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">Nome do Serviço</label>
                <input 
                  type="text" 
                  required
                  value={newService.name}
                  onChange={e => setNewService({...newService, name: e.target.value})}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: CORTE FEMININO"
                />
              </div>
              
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">Duração (Min)</label>
                  <input 
                    type="number" 
                    required
                    min="15"
                    step="15"
                    value={newService.duration_minutes}
                    onChange={e => setNewService({...newService, duration_minutes: Number(e.target.value)})}
                    className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
                <div>
                  <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">Valor (R$)</label>
                  <input 
                    type="number" 
                    required
                    min="0"
                    step="0.01"
                    value={newService.price}
                    onChange={e => setNewService({...newService, price: Number(e.target.value)})}
                    className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  />
                </div>
              </div>

              <button 
                type="submit" 
                disabled={submitting}
                className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
              >
                {submitting ? 'Salvando...' : 'Confirmar Serviço'}
              </button>
            </form>
          </div>
        </div>
      )}

      {/* PROFESSIONAL MODAL */}
      {isProfModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-md p-8 relative">
            <button 
              onClick={() => setIsProfModalOpen(false)}
              className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
            >
              ×
            </button>
            <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">Novo Profissional</h2>
            
            <form onSubmit={handleCreateProf} className="space-y-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">Nome Completo</label>
                <input 
                  type="text" 
                  required
                  value={newProf.name}
                  onChange={e => setNewProf({...newProf, name: e.target.value})}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: MARIA SILVA"
                />
              </div>
              
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">Especialidade / Cargo</label>
                <input 
                  type="text" 
                  value={newProf.role}
                  onChange={e => setNewProf({...newProf, role: e.target.value})}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
                  placeholder="EX: CABELEIREIRA"
                />
              </div>

              <button 
                type="submit" 
                disabled={submitting}
                className="w-full mt-4 flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
              >
                {submitting ? 'Salvando...' : 'Confirmar Profissional'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
