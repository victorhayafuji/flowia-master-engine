import { useCallback, useEffect, useRef, useState } from "react"
import { StepRenderer } from "./StepRenderer"
import { advance, DeviceUnauthorized, startSession, type GuidedStep } from "./totem-api"

const TOKEN_KEY = "totem_device_token"
const IDLE_MS = 90_000 // reset to the attract screen after 90s of inactivity

type Mode = "attract" | "session" | "done"

export function App() {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem(TOKEN_KEY))
  const [mode, setMode] = useState<Mode>("attract")
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [step, setStep] = useState<GuidedStep | null>(null)
  const [doneMsg, setDoneMsg] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const reset = useCallback(() => {
    setMode("attract")
    setSessionId(null)
    setStep(null)
    setDoneMsg("")
    setError(null)
    setBusy(false)
  }, [])

  // Unpair on 403 (revoked/invalid device) — sends the operator back to pairing.
  const handleUnauthorized = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    reset()
  }, [reset])

  const requestFullscreen = () => {
    try {
      void document.documentElement.requestFullscreen?.()
    } catch {
      /* not allowed / unsupported — non-fatal */
    }
  }

  const begin = async () => {
    if (!token || busy) return
    setBusy(true)
    setError(null)
    requestFullscreen()
    try {
      const res = await startSession(token)
      setSessionId(res.session_id)
      setStep(res.step)
      setMode("session")
    } catch (err) {
      if (err instanceof DeviceUnauthorized) return handleUnauthorized()
      setError(err instanceof Error ? err.message : "Erro ao iniciar.")
    } finally {
      setBusy(false)
    }
  }

  const choose = async (selection: string) => {
    if (!token || !sessionId || busy) return
    setBusy(true)
    setError(null)
    try {
      const res = await advance(token, sessionId, selection)
      if (res.done) {
        setDoneMsg(res.response)
        setMode("done")
      } else if (res.step) {
        setStep(res.step)
      } else {
        // No step and not done — treat as end of attendance.
        setDoneMsg(res.response || "")
        setMode("done")
      }
    } catch (err) {
      if (err instanceof DeviceUnauthorized) return handleUnauthorized()
      setError(err instanceof Error ? err.message : "Algo deu errado. Tente novamente.")
    } finally {
      setBusy(false)
    }
  }

  // Auto-return to attract after a terminal message.
  useEffect(() => {
    if (mode !== "done") return
    const t = window.setTimeout(reset, 5000)
    return () => window.clearTimeout(t)
  }, [mode, reset])

  // Idle reset: privacy on a shared device — no customer data lingers on screen.
  const resetRef = useRef(reset)
  resetRef.current = reset
  useEffect(() => {
    if (mode !== "session") return
    let t = window.setTimeout(() => resetRef.current(), IDLE_MS)
    const bump = () => {
      window.clearTimeout(t)
      t = window.setTimeout(() => resetRef.current(), IDLE_MS)
    }
    window.addEventListener("pointerdown", bump)
    window.addEventListener("keydown", bump)
    return () => {
      window.clearTimeout(t)
      window.removeEventListener("pointerdown", bump)
      window.removeEventListener("keydown", bump)
    }
  }, [mode, step])

  if (!token) {
    return <Pairing onPaired={(t) => setToken(t)} />
  }

  if (mode === "attract") {
    return (
      <div className="screen attract" onClick={begin}>
        <h1 className="pulse">Bem-vindo(a)!</h1>
        <p>Toque na tela para começar</p>
        {error ? <p className="error">{error}</p> : null}
      </div>
    )
  }

  if (mode === "done") {
    return (
      <div className="screen">
        <p className="success-msg">{doneMsg || "Tudo certo!"}</p>
        <p className="muted">Voltando ao início…</p>
      </div>
    )
  }

  // mode === "session"
  return (
    <>
      {step ? (
        <StepRenderer step={step} busy={busy} onSelect={choose} />
      ) : (
        <div className="screen">
          <div className="spinner" />
        </div>
      )}
      {error ? (
        <div className="screen" style={{ position: "fixed", inset: "auto 0 4vh 0", height: "auto" }}>
          <p className="error">{error}</p>
        </div>
      ) : null}
    </>
  )
}

/** Operator-only one-time pairing: paste the device token from Settings → Totem. */
function Pairing({ onPaired }: { onPaired: (token: string) => void }) {
  const [value, setValue] = useState("")
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pair = async (e: React.FormEvent) => {
    e.preventDefault()
    const candidate = value.trim()
    if (!candidate) return
    setBusy(true)
    setError(null)
    try {
      // Validate the token by starting (then discarding) a session.
      await startSession(candidate)
      localStorage.setItem(TOKEN_KEY, candidate)
      onPaired(candidate)
    } catch (err) {
      if (err instanceof DeviceUnauthorized) {
        setError("Token inválido. Verifique nas Configurações do painel.")
      } else {
        setError(err instanceof Error ? err.message : "Não foi possível parear.")
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="screen pairing" onSubmit={pair}>
      <h2>Parear este totem</h2>
      <p className="muted">Cole o token gerado em Configurações → Totem.</p>
      <div className="field">
        <input
          autoFocus
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="kdev_…"
        />
        <button type="submit" className="btn-primary" disabled={busy || !value.trim()}>
          {busy ? "Validando…" : "Parear"}
        </button>
      </div>
      {error ? <p className="error">{error}</p> : null}
    </form>
  )
}
