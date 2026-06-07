import { Outlet, Link, useLocation } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"
import { LayoutDashboard, Calendar, Settings, LogOut, Users, Database, MessageSquare } from "lucide-react"

export function Layout() {
  const { signOut, user, organizationName, organizations, organizationId, setSelectedOrgId } = useAuth()
  const location = useLocation()
  const isDev = import.meta.env.DEV

  const navItems = [
    { label: "Visão Geral", path: "/", icon: LayoutDashboard },
    { label: "Agenda", path: "/agenda", icon: Calendar },
    { label: "Clientes", path: "/patients", icon: Users },
    { label: "Catálogo", path: "/catalog", icon: Settings },
  ]

  const brandName = organizationName || "Salão"
  const roleLabel = user?.role === "super_admin" ? "Operador" : "Equipe"

  return (
    <div className="h-screen bg-slate-50 dark:bg-slate-950 flex font-sans overflow-hidden">

      <aside className="w-64 bg-[var(--surface)] border-r-4 border-[var(--border)] flex-shrink-0 flex flex-col">
        <div className="h-16 flex items-center px-6 border-b-4 border-[var(--border)] bg-[var(--accent)]">
          <h2 className="text-xl font-black tracking-tighter text-[var(--background)] uppercase truncate">
            {brandName}
          </h2>
        </div>

        {user?.role === "super_admin" && organizations.length > 1 && (
          <div className="p-4 border-b-2 border-[var(--border)]">
            <label className="block text-xs font-bold uppercase text-slate-500 mb-1">Salão ativo</label>
            <select
              value={organizationId || ""}
              onChange={(e) => setSelectedOrgId(e.target.value)}
              className="w-full border-2 border-[var(--border)] bg-[var(--surface)] px-2 py-1 font-mono text-xs"
            >
              {organizations.map((org) => (
                <option key={org.id} value={org.id}>
                  {org.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <nav className="flex-1 p-4 space-y-1">
          {navItems.map((item) => {
            const isActive = location.pathname === item.path
            return (
              <Link key={item.path} to={item.path}>
                <span className={`flex items-center gap-3 px-3 py-3 border-2 border-[var(--border)] shadow-[3px_3px_0px_0px_var(--border)] text-sm font-black uppercase transition-all ${isActive ? "bg-[var(--accent)] text-[var(--background)] shadow-[0px_0px_0px_0px_var(--border)] translate-y-1" : "bg-[var(--surface)] text-[var(--foreground)] hover:shadow-[5px_5px_0px_0px_var(--border)] hover:-translate-y-1"}`}>
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </span>
              </Link>
            )
          })}
        </nav>

        <div className="p-4 border-t-4 border-[var(--border)] bg-[var(--surface)]">
          <div className="mb-4 px-3">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-slate-500">{roleLabel}</p>
          </div>
          <div className="space-y-1">
            {isDev && user?.role === "super_admin" && (
              <>
                <Link to="/admin/data-lake">
                  <button className={`w-full flex items-center justify-start gap-3 px-3 py-2 text-sm font-bold uppercase transition-colors ${location.pathname === "/admin/data-lake" ? "text-[var(--accent)]" : "text-slate-600 dark:text-slate-400 hover:text-[var(--accent)]"}`}>
                    <Database className="w-4 h-4" /> Data Lake (dev)
                  </button>
                </Link>
                <Link to="/admin/chat-test">
                  <button className={`w-full flex items-center justify-start gap-3 px-3 py-2 text-sm font-bold uppercase transition-colors ${location.pathname === "/admin/chat-test" ? "text-[var(--accent)]" : "text-slate-600 dark:text-slate-400 hover:text-[var(--accent)]"}`}>
                    <MessageSquare className="w-4 h-4" /> Chat Test (dev)
                  </button>
                </Link>
              </>
            )}
            <button
              onClick={signOut}
              className="flex items-center gap-3 px-3 py-3 w-full border-2 border-[var(--border)] bg-[var(--foreground)] text-[var(--background)] shadow-[3px_3px_0px_0px_var(--border)] text-sm font-black uppercase transition-all hover:shadow-[5px_5px_0px_0px_var(--border)] hover:-translate-y-1 active:translate-y-1 active:shadow-none"
            >
              <LogOut className="w-4 h-4 mr-3" /> Sair
            </button>
          </div>
        </div>
      </aside>

      <main className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <Outlet />
      </main>

    </div>
  )
}
