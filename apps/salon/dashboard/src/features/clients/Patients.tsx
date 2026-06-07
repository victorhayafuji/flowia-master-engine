import { useState, useEffect } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Search, Phone, History, Plus, ArrowRight } from "lucide-react"

interface Patient {
  id: string
  name: string
  phone: string
  created_at: string
}

export function Patients() {
  const { user, organizationId, orgHeader } = useAuth()
  const [patients, setPatients] = useState<Patient[]>([])
  const [loading, setLoading] = useState(true)
  const [searchTerm, setSearchTerm] = useState("")

  // Modal states
  const [isModalOpen, setIsModalOpen] = useState(false)
  const [newName, setNewName] = useState("")
  const [newPhone, setNewPhone] = useState("")
  const [submitting, setSubmitting] = useState(false)

  useEffect(() => {
    const fetchPatients = async () => {
      if (!user || !organizationId) {
        setLoading(false)
        return
      }

      try {
        const data = await api.get('/patients/', orgHeader)
        if (data.status === 'success') {
          setPatients(data.data || [])
        }
      } catch (err) {
        console.error("Erro ao buscar pacientes:", err)
      } finally {
        setLoading(false)
      }
    }

    fetchPatients()
  }, [user, organizationId, orgHeader])

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newName || !newPhone) return
    setSubmitting(true)
    
    try {
      const response = await api.post('/patients/', { name: newName, phone: newPhone }, orgHeader)
      if (response.status === 'success' && response.data) {
        setPatients(prev => [response.data, ...prev])
        setIsModalOpen(false)
        setNewName("")
        setNewPhone("")
      }
    } catch (err) {
      console.error("Erro ao criar paciente:", err)
      alert("Erro ao criar paciente. Verifique os logs.")
    } finally {
      setSubmitting(false)
    }
  }

  const filteredPatients = patients.filter(p => 
    p.name?.toLowerCase().includes(searchTerm.toLowerCase()) || 
    p.phone?.includes(searchTerm)
  )

  return (
    <div className="page-shell">
      {/* Brutalist Header Area */}
      <div className="page-header mb-6 sm:mb-8 flex flex-col xl:flex-row xl:justify-between xl:items-end border-b-8 border-[var(--border)] pb-8">
        <div>
          <div className="flex items-center gap-4 mb-4">
            <div className="bg-[var(--foreground)] text-[var(--background)] px-3 py-1 font-mono text-xs font-bold uppercase tracking-widest">
              Módulo 01
            </div>
            <div className="h-1 flex-1 bg-[var(--border)] opacity-20"></div>
          </div>
          <h1 className="text-5xl sm:text-7xl font-black uppercase tracking-tighter text-[var(--foreground)] leading-none">
            Clientes
          </h1>
          <p className="text-[var(--foreground)]/70 font-mono mt-4 uppercase text-sm font-bold tracking-widest border-l-4 border-[var(--accent)] pl-4">
            Acesso Restrito // Registros Ativos
          </p>
        </div>
        
        <button 
          onClick={() => setIsModalOpen(true)}
          className="mt-8 xl:mt-0 flex items-center justify-between px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[8px_8px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[6px_6px_0px_0px_var(--border)] active:translate-y-[8px] active:translate-x-[8px] active:shadow-[0px_0px_0px_0px_var(--border)] transition-all group rounded-none">
          <span className="flex items-center gap-3">
            <Plus className="w-5 h-5" /> 
            Novo Registro
          </span>
        </button>
      </div>

      {/* Control Bar */}
      <div className="shrink-0 mb-6 p-6 bg-[var(--surface)] border-4 border-[var(--border)] shadow-[8px_8px_0px_0px_var(--border)] flex flex-col md:flex-row gap-6 justify-between items-center relative overflow-hidden">
        {/* Subtle background texture */}
        <div className="absolute inset-0 opacity-[0.02] pointer-events-none" style={{ backgroundImage: 'radial-gradient(var(--foreground) 1px, transparent 1px)', backgroundSize: '16px 16px' }}></div>
        
        <div className="flex items-center gap-4 z-10 w-full md:w-auto">
          <div className="w-12 h-12 bg-[var(--foreground)] flex items-center justify-center border-2 border-[var(--border)]">
            <Search className="w-6 h-6 text-[var(--background)]" />
          </div>
          <div className="flex-1">
            <input 
              type="text" 
              placeholder="Buscar por nome ou contato..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full md:w-96 bg-transparent border-b-4 border-[var(--foreground)]/20 focus:border-[var(--accent)] py-2 font-mono text-lg font-bold uppercase transition-colors focus:outline-none placeholder:text-[var(--foreground)]/30"
            />
          </div>
        </div>

        <div className="z-10 font-mono text-sm font-bold uppercase tracking-widest text-[var(--foreground)]/50 text-right w-full md:w-auto">
          Total: <span className="text-[var(--foreground)] text-xl">{filteredPatients.length}</span>
        </div>
      </div>

      {/* Brutalist Data Grid */}
      <div className="bg-[var(--surface)] border-4 border-[var(--border)] shadow-[8px_8px_0px_0px_var(--border)] relative z-10 flex flex-col min-h-0 flex-1 panel-scroll">
        
        {loading ? (
          <div className="p-12 space-y-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-20 bg-[var(--foreground)]/5 border-2 border-dashed border-[var(--foreground)]/20 animate-pulse"></div>
            ))}
          </div>
        ) : filteredPatients.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-32 border-2 border-dashed border-[var(--foreground)]/20 m-8 bg-[var(--background)]">
            <div className="text-[var(--foreground)]/20 mb-6 font-black text-6xl">∅</div>
            <p className="font-mono uppercase font-bold tracking-widest text-[var(--foreground)]/50">Base de dados vazia</p>
          </div>
        ) : (
          <div className="divide-y-4 divide-[var(--border)]">
            {filteredPatients.map((p, idx) => (
              <div 
                key={p.id} 
                className={`flex flex-col lg:flex-row items-start lg:items-center justify-between p-6 hover:bg-[var(--foreground)] hover:text-[var(--background)] transition-colors group ${idx % 2 === 0 ? 'bg-[var(--background)]' : 'bg-[var(--surface)]'}`}
              >
                <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-6 w-full">
                  
                  <div className="space-y-1">
                    <div className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/40 group-hover:text-[var(--background)]/50">Identificação</div>
                    <div className="font-black uppercase text-xl md:text-2xl tracking-tight truncate">{p.name || 'NÃO ESPECIFICADO'}</div>
                  </div>

                  <div className="space-y-1">
                    <div className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/40 group-hover:text-[var(--background)]/50">Contato</div>
                    <div className="font-mono font-bold flex items-center gap-3">
                      <Phone className="w-4 h-4 text-[var(--accent)] group-hover:text-[var(--background)]" />
                      {p.phone}
                    </div>
                  </div>

                  <div className="space-y-1">
                    <div className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/40 group-hover:text-[var(--background)]/50">Registro</div>
                    <div className="font-mono font-bold">
                      {new Date(p.created_at).toLocaleDateString('pt-BR', { day: '2-digit', month: '2-digit', year: 'numeric' })}
                    </div>
                  </div>

                </div>

                <div className="mt-6 lg:mt-0 w-full lg:w-auto">
                  <button className="w-full lg:w-auto flex items-center justify-center gap-3 px-6 py-3 border-2 border-[var(--border)] group-hover:border-[var(--background)] font-mono text-sm font-bold uppercase tracking-widest hover:bg-[var(--accent)] hover:border-[var(--accent)] hover:text-[var(--foreground)] transition-colors">
                    <History className="w-4 h-4" />
                    <span>Prontuário</span>
                    <ArrowRight className="w-4 h-4 opacity-0 -ml-4 group-hover:opacity-100 group-hover:ml-0 transition-all" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Brutalist Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm animate-in fade-in duration-200">
          <div className="bg-[var(--background)] border-4 border-[var(--border)] shadow-[12px_12px_0px_0px_var(--border)] w-full max-w-md p-8 relative">
            <button 
              onClick={() => setIsModalOpen(false)}
              className="absolute top-4 right-4 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-mono text-xl font-bold"
            >
              ×
            </button>
            <h2 className="text-3xl font-black uppercase tracking-tight text-[var(--foreground)] mb-6 border-b-4 border-[var(--border)] pb-2">Novo Cliente</h2>
            
            <form onSubmit={handleCreatePatient} className="space-y-6">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-2">Nome Completo</label>
                <input 
                  type="text" 
                  required
                  value={newName}
                  onChange={e => setNewName(e.target.value)}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-3 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 transition-all"
                  placeholder="EX: MARIA SILVA"
                />
              </div>
              
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-2">Contato / Telefone</label>
                <input 
                  type="text" 
                  required
                  value={newPhone}
                  onChange={e => setNewPhone(e.target.value)}
                  className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-3 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent)]/20 transition-all"
                  placeholder="EX: (11) 99999-9999"
                />
              </div>

              <button 
                type="submit" 
                disabled={submitting}
                className="w-full flex justify-center items-center gap-3 px-6 py-4 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[6px_6px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[4px_4px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
              >
                {submitting ? 'Salvando...' : 'Confirmar Registro'}
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
