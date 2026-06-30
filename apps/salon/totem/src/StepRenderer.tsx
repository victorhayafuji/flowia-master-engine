import { useState } from "react"
import type { GuidedStep } from "./totem-api"

interface Props {
  step: GuidedStep
  busy: boolean
  onSelect: (optionId: string) => void
}

/** Renders one StructuredStep as large touch targets (buttons/list) or a text field (input). */
export function StepRenderer({ step, busy, onSelect }: Props) {
  if (step.kind === "input") {
    return <InputStep step={step} busy={busy} onSubmit={onSelect} />
  }
  return (
    <div className="screen">
      <p className="prompt">{step.text}</p>
      <div className="options">
        {step.options.map((opt) => (
          <button
            key={opt.id}
            className="opt"
            disabled={busy}
            onClick={() => onSelect(opt.id)}
          >
            <span>{opt.title}</span>
            {opt.description ? <span className="desc">{opt.description}</span> : null}
          </button>
        ))}
      </div>
    </div>
  )
}

function InputStep({ step, busy, onSubmit }: { step: GuidedStep; busy: boolean; onSubmit: (v: string) => void }) {
  const [value, setValue] = useState("")
  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    const v = value.trim()
    if (v) onSubmit(v)
  }
  return (
    <form className="screen" onSubmit={submit}>
      <p className="prompt">{step.text}</p>
      <div className="field">
        <input
          autoFocus
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Toque para digitar"
          enterKeyHint="send"
        />
        <button type="submit" className="btn-primary" disabled={busy || !value.trim()}>
          Continuar
        </button>
      </div>
    </form>
  )
}
