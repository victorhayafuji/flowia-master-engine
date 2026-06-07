import { useRef, useState } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MessageSquare, Send } from "lucide-react"

interface ChatMessage {
  role: "user" | "agent"
  content: string
  meta?: {
    agent?: string
    tokens_used?: number
    tokens_in?: number
    tokens_out?: number
    estimated_cost_brl?: number
    thread_id?: string
  }
}

const SUGGESTIONS = [
  "Quanto custa corte feminino?",
  "Vocês fazem coloração? Qual o preço?",
  "Quero agendar manicure amanhã",
  "Qual a política de cancelamento?",
]

export function ChatTest() {
  const { user, organizationId, orgHeader } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [sending, setSending] = useState(false)
  const threadIdRef = useRef<string | undefined>(undefined)

  const orgId = organizationId
  const canChat = Boolean(orgId)

  const sendMessage = async (text: string) => {
    if (!text.trim() || !orgId) return

    setSending(true)
    setMessages((prev) => [...prev, { role: "user", content: text.trim() }])
    setInput("")

    try {
      const res = await api.post(
        "/chat/test",
        { message: text.trim(), thread_id: threadIdRef.current },
        orgHeader
      )
      threadIdRef.current = res.thread_id
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: res.response,
          meta: {
            agent: res.agent,
            tokens_used: res.tokens_used,
            tokens_in: res.tokens_in,
            tokens_out: res.tokens_out,
            estimated_cost_brl: res.estimated_cost_brl,
            thread_id: res.thread_id,
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
            Chat Test
          </h1>
          <p className="text-slate-500 font-mono text-sm mt-1">
            Playground E2E — recepcionista + agendamento com RAG
          </p>
        </div>

        {!canChat && (
          <Card className="border-2 border-amber-500">
            <CardContent className="pt-4 font-mono text-sm">
              Selecione ou vincule uma organização para testar o chat. Super admins precisam de
              uma org específica (não ALL).
            </CardContent>
          </Card>
        )}

        <Card className="border-2 border-[var(--border)]">
          <CardHeader>
            <CardTitle className="font-black uppercase text-sm">Sugestões de teste</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                type="button"
                disabled={!canChat || sending}
                onClick={() => sendMessage(s)}
                className="px-3 py-1 border-2 border-[var(--border)] font-mono text-xs hover:bg-[var(--accent)] hover:text-[var(--background)] disabled:opacity-50"
              >
                {s}
              </button>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card className="border-2 border-[var(--border)] flex flex-col min-h-0 flex-1">
        <CardContent className="flex flex-col flex-1 min-h-0 pt-4 gap-4">
          <div className="panel-scroll flex-1 min-h-0 space-y-3">
            {messages.length === 0 && (
              <p className="font-mono text-sm text-slate-500">
                Envie uma pergunta sobre serviços ou preços para validar o RAG.
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={`p-3 border-2 font-mono text-sm whitespace-pre-wrap ${
                  m.role === "user"
                    ? "border-[var(--accent)] bg-slate-50 dark:bg-slate-900 ml-8"
                    : "border-[var(--border)] bg-[var(--surface)] mr-8"
                }`}
              >
                <span className="block text-xs uppercase text-slate-400 mb-1">
                  {m.role === "user" ? "Você" : "Agente"}
                </span>
                {m.content}
                {m.meta && (
                  <span className="block text-xs text-slate-400 mt-2">
                    agent={m.meta.agent} | tokens={m.meta.tokens_used ?? 0} (in{" "}
                    {m.meta.tokens_in ?? 0} / out {m.meta.tokens_out ?? 0}) | ~R${" "}
                    {(m.meta.estimated_cost_brl ?? 0).toFixed(4)}
                    {m.meta.thread_id ? ` | thread=${m.meta.thread_id.slice(0, 8)}...` : ""}
                  </span>
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
