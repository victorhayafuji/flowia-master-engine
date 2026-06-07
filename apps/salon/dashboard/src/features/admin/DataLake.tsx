import { useCallback, useEffect, useState } from "react"
import { useAuth } from "@/features/auth/AuthContext"
import { api } from "@/shared/lib/api"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Database, Upload, RefreshCw, Search, FileText } from "lucide-react"

interface PipelineStatus {
  bronze_pending: number
  bronze_processing: number
  bronze_completed: number
  bronze_error: number
  silver_ready: number
  silver_completed: number
  gold_vectors: number
}

interface BronzeDocument {
  id: string
  file_name: string
  status: string
  mime_type?: string
  file_size?: number
  created_at?: string
  error_message?: string
}

export function DataLake() {
  const { user, organizationId, orgHeader } = useAuth()
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [documents, setDocuments] = useState<BronzeDocument[]>([])
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState<{ content: string; similarity?: number }[]>([])
  const [searching, setSearching] = useState(false)

  const fetchData = useCallback(async () => {
    if (!user) return
    try {
      const [statusRes, docsRes] = await Promise.all([
        api.get("/lakehouse/status", orgHeader),
        api.get("/lakehouse/documents?limit=15", orgHeader),
      ])
      setStatus(statusRes.data)
      setDocuments(docsRes.data || [])
    } catch (err) {
      console.error("Erro ao carregar Data Lake:", err)
    } finally {
      setLoading(false)
    }
  }, [user, orgHeader])

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 15000)
    return () => clearInterval(interval)
  }, [fetchData])

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file || !organizationId) return

    setUploading(true)
    try {
      const formData = new FormData()
      formData.append("file", file)
      await api.upload("/lakehouse/upload", formData, orgHeader)
      await fetchData()
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Erro no upload"
      alert(msg)
    } finally {
      setUploading(false)
      e.target.value = ""
    }
  }

  const handleSync = async () => {
    setSyncing(true)
    try {
      await api.post("/lakehouse/sync", {}, orgHeader)
      setTimeout(fetchData, 2000)
    } catch (err) {
      console.error("Erro ao sincronizar:", err)
    } finally {
      setSyncing(false)
    }
  }

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await api.post("/lakehouse/search", { query: searchQuery }, orgHeader)
      setSearchResults(res.results || [])
    } catch (err) {
      console.error("Erro na busca:", err)
    } finally {
      setSearching(false)
    }
  }

  const statusColor = (s: string) => {
    if (s === "COMPLETED") return "text-green-600"
    if (s === "ERROR") return "text-red-600"
    if (s === "PENDING" || s === "PROCESSING") return "text-amber-600"
    return "text-slate-600"
  }

  if (!organizationId) {
    return (
      <div className="p-8">
        <p className="font-mono text-sm">Usuário sem organização vinculada. Contate o administrador.</p>
      </div>
    )
  }

  return (
    <div className="page-shell">
      <div className="page-header space-y-8 shrink-0">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-black uppercase tracking-tight flex items-center gap-3">
              <Database className="w-8 h-8 text-[var(--accent)]" />
              Data Lake
            </h1>
            <p className="text-slate-500 font-mono text-sm mt-1">
              Bronze → Silver (OCR) → Gold (Vetores RAG)
            </p>
          </div>
          <div className="flex gap-2">
            <label className="cursor-pointer">
              <input
                type="file"
                className="hidden"
                accept=".png,.jpg,.jpeg,.webp,.pdf,.txt,.md"
                onChange={handleUpload}
                disabled={uploading || !organizationId}
              />
              <span className="inline-flex items-center gap-2 px-4 py-2 border-2 border-[var(--border)] bg-[var(--foreground)] text-[var(--background)] font-black uppercase text-xs shadow-[4px_4px_0px_0px_var(--accent)]">
                <Upload className="w-4 h-4" />
                {uploading ? "Enviando..." : "Upload"}
              </span>
            </label>
            <Button onClick={handleSync} disabled={syncing} variant="outline" className="font-black uppercase text-xs">
              <RefreshCw className={`w-4 h-4 mr-2 ${syncing ? "animate-spin" : ""}`} />
              Processar
            </Button>
          </div>
        </div>

        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-4">
          {[
            { label: "Bronze Pendente", value: status?.bronze_pending ?? 0, layer: "🥉" },
            { label: "Silver Pronto", value: status?.silver_ready ?? 0, layer: "🥈" },
            { label: "Gold Vetores", value: status?.gold_vectors ?? 0, layer: "🥇" },
            { label: "Erros", value: status?.bronze_error ?? 0, layer: "⚠️" },
          ].map((item) => (
            <Card key={item.label} className="border-2 border-[var(--border)] shadow-[4px_4px_0px_0px_var(--border)]">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs font-mono uppercase">{item.layer} {item.label}</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-3xl font-black">{loading ? "—" : item.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-2 flex-1 min-h-0">
        <Card className="border-2 border-[var(--border)] flex flex-col min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle className="flex items-center gap-2 font-black uppercase text-sm">
              <FileText className="w-4 h-4" /> Documentos Bronze
            </CardTitle>
          </CardHeader>
          <CardContent className="panel-scroll flex-1 min-h-0">
            {documents.length === 0 ? (
              <p className="font-mono text-sm text-slate-500">Nenhum documento ingerido ainda.</p>
            ) : (
              <ul className="space-y-2">
                {documents.map((doc) => (
                  <li
                    key={doc.id}
                    className="flex justify-between items-center p-3 border-2 border-[var(--border)] bg-[var(--surface)]"
                  >
                    <div>
                      <p className="font-mono text-sm font-bold truncate max-w-[200px]">{doc.file_name}</p>
                      <p className={`text-xs font-mono uppercase ${statusColor(doc.status)}`}>{doc.status}</p>
                    </div>
                    <span className="text-xs font-mono text-slate-400">
                      {doc.file_size ? `${Math.round(doc.file_size / 1024)}KB` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>

        <Card className="border-2 border-[var(--border)] flex flex-col min-h-0">
          <CardHeader className="shrink-0">
            <CardTitle className="flex items-center gap-2 font-black uppercase text-sm">
              <Search className="w-4 h-4" /> Busca Semântica (Gold)
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col flex-1 min-h-0 gap-4">
            <form onSubmit={handleSearch} className="flex gap-2 shrink-0">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ex: quanto custa corte feminino"
                className="flex-1 px-3 py-2 border-2 border-[var(--border)] font-mono text-sm bg-[var(--surface)]"
              />
              <Button type="submit" disabled={searching} className="font-black uppercase text-xs">
                {searching ? "..." : "Buscar"}
              </Button>
            </form>
            {searchResults.length > 0 && (
              <ul className="space-y-2 panel-scroll flex-1 min-h-0">
                {searchResults.map((r, i) => {
                  const preview =
                    r.content.length > 300 ? `${r.content.slice(0, 300)}...` : r.content
                  return (
                    <li
                      key={i}
                      className="p-2 border-l-4 border-[var(--accent)] bg-slate-50 dark:bg-slate-900 font-mono text-xs whitespace-pre-wrap"
                    >
                      {preview}
                      {r.similarity != null && (
                        <span className="block text-slate-400 mt-1">
                          similaridade: {(r.similarity * 100).toFixed(0)}%
                        </span>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
