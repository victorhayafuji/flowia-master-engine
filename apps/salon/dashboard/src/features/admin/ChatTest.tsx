import { useEffect, useRef, useState } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MessageSquare, Send, User } from "lucide-react"

interface PatientOption {
  id: string
  name: string
}

interface GuidedOption {
  id: string
  title: string
  description?: string | null
}

interface GuidedStep {
  step: string
  text: string
  kind: "list" | "buttons" | "input"
  options: GuidedOption[]
}

interface ChatMessage {
  role: "user" | "agent"
  content: string
  step?: GuidedStep | null
  meta?: {
    agent?: string
    tokens_used?: number
    tokens_in?: number
    tokens_out?: number
    estimated_cost_brl?: number
    thread_id?: string
    scheduling_path?: string | null
    triage_source?: string | null
  }
}

function PathBadge({ path }: { path: string }) {
  const isDeterministic = path === "deterministic"
  return (
    <span
      className={`inline-block px-1.5 py-0.5 border-2 text-[10px] font-black uppercase ${
        isDeterministic
          ? "border-[var(--success)] text-[var(--success)]"
          : "border-[var(--accent)] text-[var(--accent)]"
      }`}
    >
      path={path}
    </span>
  )
}

function TriageBadge({ source }: { source: string }) {
  return (
    <span className="inline-block px-1.5 py-0.5 border border-[var(--border)] text-[var(--muted)] text-[10px] font-black uppercase">
      triage={source}
    </span>
  )
}

export function ChatTest() {
  const { user, organizationId, orgHeader } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const [patients, setPatients] = useState<PatientOption[]>([])
  // "" simulates an unregistered client (onboarding flow); a UUID simulates the
  // phone-identified client on WhatsApp.
  const [patientId, setPatientId] = useState("")
  const threadIdRef = useRef<string | undefined>(undefined)

  const orgId = organizationId
  const canChat = Boolean(orgId)
  // Telemetria de dev (path/triage/tokens/custo) é só para o operador da plataforma.
  const isSuperAdmin = user?.role === "super_admin"

  useEffect(() => {
    if (!canChat) return
    let cancelled = false
    api
      .get("/patients/", orgHeader)
      .then((res) => {
        if (!cancelled) setPatients(res?.data || res || [])
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [canChat, orgHeader])

  // Switching the simulated client starts a fresh conversation (new identity).
  const handlePatientChange = (id: string) => {
    setPatientId(id)
    setMessages([])
    threadIdRef.current = undefined
  }

  // `sentValue` goes to the backend; `displayText` (option title) is shown in the bubble.
  const sendMessage = async (sentValue: string, displayText?: string) => {
    if (!sentValue.trim() || !orgId) return

    setSending(true)
    setMessages((prev) => [...prev, { role: "user", content: (displayText || sentValue).trim() }])
    setInput("")

    try {
      const res = await api.post(
        "/chat/test",
        {
          message: sentValue.trim(),
          thread_id: threadIdRef.current,
          guided: true,
          patient_id: patientId || null,
        },
        orgHeader
      )
      threadIdRef.current = res.thread_id
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: res.response,
          step: res.step ?? null,
          meta: {
            agent: res.agent,
            tokens_used: res.tokens_used,
            tokens_in: res.tokens_in,
            tokens_out: res.tokens_out,
            estimated_cost_brl: res.estimated_cost_brl,
            thread_id: res.thread_id,
            scheduling_path: res.scheduling_path,
            triage_source: res.triage_source,
          },
        },
      ])
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao enviar mensagem"
      setMessages((prev) => [...prev, { role: "agent", content: `Erro: ${msg}` }])
    } finally {
      setSending(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    sendMessage(input)
  }

  if (!user) return null

  return (
    <div className="page-shell max-w-3xl">
      <div className="page-header space-y-6 shrink-0">
        <div>
          <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
            <MessageSquare className="w-8 h-8 text-[var(--accent)]" />
            Ensaie seu assistente
          </h1>
          <p className="text-[var(--muted)] font-mono text-sm mt-1">
            Converse como se fosse um cliente e veja como o assistente responde, tira dúvidas e agenda.
          </p>
        </div>

        {!canChat && (
          <Card className="border border-[var(--warning)]">
            <CardContent className="pt-4 font-mono text-sm">
              Selecione ou vincule uma organização para testar o chat. Super admins precisam de
              uma org específica (não ALL).
            </CardContent>
          </Card>
        )}

        <Card className="border-2 border-[var(--border)]">
          <CardHeader>
            <CardTitle className="font-black uppercase text-sm flex items-center gap-2">
              <User className="w-4 h-4 text-[var(--accent)]" />
              Cliente (simulação)
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="font-mono text-xs text-[var(--muted)]">
              No WhatsApp real o cliente é identificado pelo telefone. Aqui você simula: escolha um
              cliente cadastrado ou "não cadastrado" para testar o onboarding.
            </p>
            <select
              value={patientId}
              onChange={(e) => handlePatientChange(e.target.value)}
              disabled={!canChat}
              aria-label="Cliente simulado"
              data-testid="chat-patient-select"
              className="block w-full max-w-sm bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono text-sm focus:outline-none focus:border-[var(--accent)]"
            >
              <option value="">Cliente não cadastrado (onboarding)</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </CardContent>
        </Card>
      </div>

      <Card className="border-2 border-[var(--border)] flex flex-col min-h-0 flex-1">
        <CardContent className="flex flex-col flex-1 min-h-0 pt-4 gap-4">
          <div className="panel-scroll flex-1 min-h-0 space-y-3">
            {messages.length === 0 && (
              <p className="font-mono text-sm text-[var(--muted)]">
                Envie uma pergunta sobre serviços ou preços para validar o RAG.
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`p-3 border-2 font-mono text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "border-[var(--accent)] bg-[var(--surface-glass)] ml-8"
                    : "border-[var(--border)] bg-[var(--surface)] mr-8"
                }`}
              >
                <span className="block text-xs uppercase text-[var(--muted)] mb-1">
                  {m.role === "user" ? "Você" : "Agente"}
                </span>
                {m.content}
                {m.role === "agent" &&
                  i === messages.length - 1 &&
                  m.step &&
                  m.step.options.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {m.step.options.map((opt) => (
                        <button
                          key={opt.id}
                          type="button"
                          disabled={!canChat || sending}
                          onClick={() => sendMessage(opt.id, opt.title)}
                          className="px-3 py-2 border-2 border-[var(--border)] font-mono text-xs text-left hover:border-[var(--accent)] hover:text-[var(--accent)] disabled:opacity-50"
                          data-testid={`guided-option-${opt.id}`}
                        >
                          <span className="block font-bold">{opt.title}</span>
                          {opt.description && (
                            <span className="block text-[10px] text-[var(--foreground)]/60">
                              {opt.description}
                            </span>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                {isSuperAdmin && m.meta && (
                  <div className="mt-2 space-y-1">
                    {(m.meta.scheduling_path || m.meta.triage_source) && (
                      <div className="flex flex-wrap gap-1">
                        {m.meta.scheduling_path && <PathBadge path={m.meta.scheduling_path} />}
                        {m.meta.triage_source && <TriageBadge source={m.meta.triage_source} />}
                      </div>
                    )}
                    <span className="block text-xs text-[var(--muted)]">
                      agent={m.meta.agent} | tokens={m.meta.tokens_used ?? 0} (in{" "}
                      {m.meta.tokens_in ?? 0} / out {m.meta.tokens_out ?? 0}) | ~R${" "}
                      {(m.meta.estimated_cost_brl ?? 0).toFixed(4)}
                      {m.meta.thread_id ? ` | thread=${m.meta.thread_id.slice(0, 8)}...` : ""}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>

          <form onSubmit={handleSubmit} className="flex gap-2 border-t-2 border-[var(--border)] pt-4">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ex: Quanto custa corte feminino?"
              disabled={!canChat || sending}
              className="flex-1 px-3 py-2 border-2 border-[var(--border)] font-mono text-sm bg-[var(--surface)]"
            />
            <Button type="submit" disabled={!canChat || sending} className="font-black uppercase text-xs">
              <Send className="w-4 h-4 mr-1" />
              {sending ? "..." : "Enviar"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
