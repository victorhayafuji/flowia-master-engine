import { useCallback, useEffect, useState } from "react"
import {
  AlertCircle,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
  Loader2,
  MessageCircle,
} from "lucide-react"
import { useAuth } from "@/features/auth/AuthContext"
import { PageHeader } from "@/components/PageHeader"
import { getWhatsAppConfig, testWhatsAppConfig, updateWhatsAppConfig } from "@/shared/lib/api"
import { buildWebhookUrl } from "./lib/webhookUrl"

// The webhook URL must always point at the public API (Meta can't reach localhost).
// The backend is the source of truth (GET → webhook_url); this is only a non-localhost fallback.
const PUBLIC_API_FALLBACK = "https://flowia-api.onrender.com/api/v1"

const inputClass =
  "w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono text-xs font-bold focus:outline-none focus:border-[var(--accent)]"

interface TestResult {
  ok: boolean
  verified_name?: string | null
  display_phone_number?: string | null
  error?: string | null
}

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard may be unavailable (insecure context) — fail silently.
    }
  }
  return (
    <div>
      <label className="block font-mono text-[10px] font-bold uppercase tracking-widest text-[var(--foreground)]/60 mb-1">
        {label}
      </label>
      <div className="flex items-stretch gap-2">
        <code className="flex-1 min-w-0 truncate bg-[var(--background)] border-2 border-[var(--border)] px-2 py-2 font-mono text-xs">
          {value}
        </code>
        <button
          type="button"
          onClick={copy}
          aria-label={`Copiar ${label}`}
          className="shrink-0 flex items-center gap-1 border-2 border-[var(--border)] bg-[var(--surface)] px-3 font-mono text-[10px] font-bold uppercase hover:bg-[var(--accent)] hover:text-[var(--background)] transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copiado" : "Copiar"}
        </button>
      </div>
    </div>
  )
}

export function Settings() {
  const { orgHeader, organizationId } = useAuth()
  const [loading, setLoading] = useState(true)
  const [phoneId, setPhoneId] = useState("")
  const [businessId, setBusinessId] = useState("")
  const [token, setToken] = useState("")
  const [tokenConfigured, setTokenConfigured] = useState(false)
  const [tokenPreview, setTokenPreview] = useState<string | null>(null)
  const [verifyToken, setVerifyToken] = useState("")
  const [webhookUrl, setWebhookUrl] = useState(() => buildWebhookUrl(PUBLIC_API_FALLBACK))
  const [showHelp, setShowHelp] = useState(false)

  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<TestResult | null>(null)
  const [feedback, setFeedback] = useState<{ kind: "ok" | "error"; msg: string } | null>(null)

  const loadConfig = useCallback(async () => {
    if (!organizationId) {
      setLoading(false)
      return
    }
    try {
      const res = await getWhatsAppConfig(orgHeader)
      const data = res?.data || {}
      setPhoneId(data.whatsapp_phone_id || "")
      setBusinessId(data.whatsapp_business_id || "")
      setTokenConfigured(Boolean(data.token_configured))
      setTokenPreview(data.token_preview || null)
      setVerifyToken(data.verify_token || "")
      setWebhookUrl(data.webhook_url || buildWebhookUrl(PUBLIC_API_FALLBACK))
      setToken("")
    } catch (err) {
      console.error("Erro ao carregar configuração do WhatsApp:", err)
    } finally {
      setLoading(false)
    }
  }, [orgHeader, organizationId])

  useEffect(() => {
    void loadConfig()
  }, [loadConfig])

  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    setFeedback(null)
    try {
      const res = await testWhatsAppConfig(
        { whatsapp_phone_id: phoneId.trim(), whatsapp_access_token: token.trim() },
        orgHeader,
      )
      setTestResult(res?.data as TestResult)
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Falha ao testar conexão."
      setTestResult({ ok: false, error: msg })
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setFeedback(null)
    try {
      await updateWhatsAppConfig(
        {
          whatsapp_phone_id: phoneId.trim(),
          whatsapp_business_id: businessId.trim(),
          whatsapp_access_token: token.trim(), // blank = backend keeps the current token
        },
        orgHeader,
      )
      setFeedback({ kind: "ok", msg: "Configuração salva com sucesso." })
      setTestResult(null)
      await loadConfig()
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro ao salvar."
      setFeedback({ kind: "error", msg })
    } finally {
      setSaving(false)
    }
  }

  // Status banner derivation.
  let status: { kind: "connected" | "error" | "configured" | "empty"; text: string }
  if (testResult?.ok) {
    const name = testResult.verified_name || "Conta verificada"
    const phone = testResult.display_phone_number ? ` · ${testResult.display_phone_number}` : ""
    status = { kind: "connected", text: `Conectado: ${name}${phone}` }
  } else if (testResult && !testResult.ok) {
    status = { kind: "error", text: testResult.error || "Não foi possível conectar." }
  } else if (tokenConfigured && phoneId) {
    status = { kind: "configured", text: "Credenciais salvas. Clique em “Testar conexão” para validar." }
  } else {
    status = { kind: "empty", text: "WhatsApp ainda não configurado." }
  }

  const statusStyles: Record<typeof status.kind, string> = {
    connected: "border-green-600 bg-green-600/10 text-green-700 dark:text-green-400",
    error: "border-red-600 bg-red-600/10 text-red-700 dark:text-red-400",
    configured: "border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--foreground)]",
    empty: "border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)]/70",
  }

  return (
    <div className="page-shell">
      <PageHeader title="Configurações" subtitle="Integração WhatsApp" />

      {loading ? (
        <div className="border-4 border-[var(--border)] bg-[var(--surface)] flex-1 min-h-[200px] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-[var(--accent)]" />
        </div>
      ) : (
        <div className="panel-scroll">
          <div className="max-w-2xl space-y-6 pb-8">
            {/* Status banner */}
            <div
              className={`flex items-center gap-3 border-4 p-4 font-mono text-sm font-bold ${statusStyles[status.kind]}`}
            >
              {status.kind === "connected" ? (
                <CheckCircle2 className="w-5 h-5 shrink-0" />
              ) : status.kind === "error" ? (
                <AlertCircle className="w-5 h-5 shrink-0" />
              ) : (
                <MessageCircle className="w-5 h-5 shrink-0" />
              )}
              <span className="min-w-0">{status.text}</span>
            </div>

            {/* Guided "how to connect" card */}
            <div className="border-4 border-[var(--border)] bg-[var(--surface)]">
              <button
                type="button"
                onClick={() => setShowHelp((v) => !v)}
                className="w-full flex items-center justify-between px-4 py-3 border-b-4 border-[var(--border)] bg-[var(--background)] font-black uppercase tracking-widest text-sm"
              >
                Como conectar meu WhatsApp
                {showHelp ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </button>
              {showHelp && (
                <div className="p-4 space-y-4">
                  <ol className="list-decimal pl-5 space-y-2 font-mono text-xs text-[var(--foreground)]/80">
                    <li>
                      Acesse o <strong>Meta for Developers</strong> (developers.facebook.com) e abra seu
                      app de WhatsApp Business.
                    </li>
                    <li>
                      Em <strong>WhatsApp → Configuração da API</strong>, copie o{" "}
                      <strong>Identificador do número de telefone</strong> (phone number ID) e cole no
                      campo abaixo.
                    </li>
                    <li>
                      Gere um <strong>token de acesso permanente</strong> (token de usuário do sistema) e
                      cole no campo Token.
                    </li>
                    <li>
                      Em <strong>Configuração do Webhook</strong>, cole a URL e o Token de verificação
                      abaixo, e assine o evento <strong>messages</strong>.
                    </li>
                    <li>Clique em “Testar conexão” e depois em “Salvar”.</li>
                  </ol>
                  <div className="space-y-3 border-t-2 border-[var(--border)] pt-4">
                    <CopyField label="URL do Webhook (Callback URL)" value={webhookUrl} />
                    {verifyToken && (
                      <CopyField label="Token de verificação (Verify Token)" value={verifyToken} />
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Credentials form */}
            <form onSubmit={handleSave} className="border-4 border-[var(--border)] bg-[var(--surface)] p-4 space-y-4">
              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  Identificador do número (Phone Number ID)
                </label>
                <input
                  type="text"
                  value={phoneId}
                  onChange={(e) => setPhoneId(e.target.value)}
                  className={inputClass}
                  placeholder="123456789012345"
                  autoComplete="off"
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  Token de acesso
                </label>
                <input
                  type="password"
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                  className={inputClass}
                  placeholder={tokenConfigured ? `${tokenPreview || "••••"} — deixe em branco para manter` : "Cole o token permanente"}
                  autoComplete="off"
                />
              </div>

              <div>
                <label className="block font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70 mb-1">
                  ID da conta comercial (Business ID) — opcional
                </label>
                <input
                  type="text"
                  value={businessId}
                  onChange={(e) => setBusinessId(e.target.value)}
                  className={inputClass}
                  placeholder="opcional"
                  autoComplete="off"
                />
              </div>

              <div className="flex flex-col sm:flex-row gap-3 pt-2">
                <button
                  type="button"
                  onClick={handleTest}
                  disabled={testing || saving}
                  className="flex-1 flex justify-center items-center gap-2 px-4 py-3 bg-[var(--surface)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[4px_4px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
                >
                  {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {testing ? "Testando..." : "Testar conexão"}
                </button>
                <button
                  type="submit"
                  disabled={saving || testing}
                  className="flex-1 flex justify-center items-center gap-2 px-4 py-3 bg-[var(--accent)] text-[var(--foreground)] font-black uppercase tracking-widest border-4 border-[var(--border)] shadow-[4px_4px_0px_0px_var(--border)] hover:translate-y-[2px] hover:translate-x-[2px] hover:shadow-[2px_2px_0px_0px_var(--border)] disabled:opacity-50 transition-all"
                >
                  {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null}
                  {saving ? "Salvando..." : "Salvar"}
                </button>
              </div>

              {feedback && (
                <p
                  className={`font-mono text-xs font-bold ${
                    feedback.kind === "ok" ? "text-green-700 dark:text-green-400" : "text-red-700 dark:text-red-400"
                  }`}
                >
                  {feedback.msg}
                </p>
              )}
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
