export function SelectOrQuickAdd({
  label,
  type,
  quickAdd,
  setQuickAdd,
  quickData,
  setQuickData,
  onQuickSave,
  value,
  onChange,
  options,
  showPhone,
  showDuration,
}: {
  label: string
  type: "patient" | "professional" | "service"
  quickAdd: { type: "patient" | "professional" | "service" | null; loading: boolean }
  setQuickAdd: React.Dispatch<React.SetStateAction<{ type: "patient" | "professional" | "service" | null; loading: boolean }>>
  quickData: Record<string, string>
  setQuickData: React.Dispatch<React.SetStateAction<Record<string, string>>>
  onQuickSave: () => void
  value: string
  onChange: (v: string) => void
  options: Array<{ id: string; name: string; duration_minutes?: number }>
  showPhone?: boolean
  showDuration?: boolean
}) {
  return (
    <div>
      <div className="flex justify-between items-center mb-1">
        <label className="font-mono text-xs font-bold uppercase tracking-widest text-[var(--foreground)]/70">{label}</label>
        {quickAdd.type !== type && (
          <button
            type="button"
            onClick={() => setQuickAdd({ type, loading: false })}
            className="text-xs font-bold text-[var(--accent)] hover:underline"
          >
            + NOVO
          </button>
        )}
      </div>
      {quickAdd.type === type ? (
        <div className="flex gap-2">
          <input
            type="text"
            placeholder={`NOME DO ${label.toUpperCase()}`}
            value={quickData.name || ""}
            onChange={(e) => setQuickData({ ...quickData, name: e.target.value })}
            className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
          />
          {showPhone && (
            <input
              type="text"
              placeholder="TELEFONE"
              value={quickData.phone || ""}
              onChange={(e) => setQuickData({ ...quickData, phone: e.target.value })}
              className="w-32 bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
            />
          )}
          {showDuration && (
            <input
              type="number"
              placeholder="MIN"
              value={quickData.duration_minutes || ""}
              onChange={(e) => setQuickData({ ...quickData, duration_minutes: e.target.value })}
              className="w-20 bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
            />
          )}
          <button
            type="button"
            onClick={onQuickSave}
            disabled={quickAdd.loading}
            className="bg-[var(--accent)] text-[var(--background)] px-4 font-bold border-2 border-[var(--border)]"
          >
            SALVAR
          </button>
          <button
            type="button"
            onClick={() => setQuickAdd({ type: null, loading: false })}
            className="px-2 text-[var(--foreground)]/50 hover:text-[var(--foreground)] font-bold"
          >
            X
          </button>
        </div>
      ) : (
        <select
          required
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-[var(--surface)] border-2 border-[var(--border)] p-2 font-mono font-bold uppercase focus:outline-none focus:border-[var(--accent)]"
        >
          <option value="">Selecione...</option>
          {options.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
              {showDuration && p.duration_minutes ? ` (${p.duration_minutes} min)` : ""}
            </option>
          ))}
        </select>
      )}
    </div>
  )
}
