import { useEffect, useState } from "react"
import { Outlet, Link, useLocation } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"
import { LayoutDashboard, Calendar, Settings, LogOut, Users, Database, MessageSquare, MessageCircle, Activity, Menu, X } from "lucide-react"
import { Wordmark } from "@/components/ui/Wordmark"

export function Layout() {
  const { signOut, user, organizations, organizationId, setSelectedOrgId } = useAuth()
  const location = useLocation()
  const isDev = import.meta.env.DEV
  const [navOpen, setNavOpen] = useState(false)

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setNavOpen(false)
  }, [location.pathname])

  // Close the mobile drawer on Escape.
  useEffect(() => {
    if (!navOpen) return
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setNavOpen(false)
    }
    document.addEventListener("keydown", onKeyDown)
    return () => document.removeEventListener("keydown", onKeyDown)
  }, [navOpen])

  const isProfessional = user?.role === "professional"

  const navItems = [
    { label: "Visão Geral", path: "/", icon: LayoutDashboard },
    { label: "Agenda", path: "/agenda", icon: Calendar },
    // Professionals see only their schedule — no client list or catalog management.
    ...(isProfessional
      ? []
      : [
          { label: "Clientes", path: "/patients", icon: Users },
          { label: "Catálogo", path: "/catalog", icon: Settings },
          { label: "Configurações", path: "/settings", icon: MessageCircle },
          { label: "Ensaie o assistente", path: "/chat-test", icon: MessageSquare },
        ]),
  ]

  const roleLabel =
    user?.role === "super_admin" ? "Operador" : isProfessional ? "Profissional" : "Equipe"

  return (
    <div className="h-screen flex flex-col bg-[var(--background)] bg-glow font-sans overflow-hidden">

      {/* Tri-color GAUSSIX brand bar pinned to the very top. */}
      <div className="brand-bar h-1 w-full shrink-0" aria-hidden="true" />

      <div className="flex flex-1 min-h-0 flex-col md:flex-row">

      {/* Mobile top bar with hamburger — hidden on md+.
          Hidden (not unmounted) while the drawer is open: without this, the header's
          own "FlowIA" wordmark stays mounted behind the drawer and — since the old
          glass-panel background was translucent — rendered as a duplicated wordmark. */}
      <header
        className={`md:hidden shrink-0 h-14 flex items-center gap-3 px-4 pt-[env(safe-area-inset-top)] border-b border-[var(--border)] glass-panel rounded-none ${
          navOpen ? "invisible" : ""
        }`}
      >
        <button
          type="button"
          aria-label="Abrir menu"
          onClick={() => setNavOpen(true)}
          className="flex items-center justify-center w-10 h-10 -ml-1 text-[var(--foreground)]"
        >
          <Menu className="w-6 h-6" />
        </button>
        <Wordmark size="sm" />
      </header>

      {/* Backdrop behind the mobile drawer — opaque + blurred enough to read as
          "content is blocked", not just decoratively tinted. */}
      {navOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm md:hidden"
          onClick={() => setNavOpen(false)}
          aria-hidden="true"
          data-testid="mobile-drawer-backdrop"
        />
      )}

      <aside
        data-testid="mobile-drawer"
        className={`fixed md:static inset-y-0 left-0 z-50 w-64 max-w-[85%] glass-overlay rounded-none border-r border-[var(--border)] flex-shrink-0 flex flex-col transform transition-transform duration-200 md:translate-x-0 ${
          navOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="h-16 flex items-center justify-between px-6 pt-[env(safe-area-inset-top)] border-b border-[var(--border)]">
          <Wordmark size="md" />
          <button
            type="button"
            aria-label="Fechar menu"
            onClick={() => setNavOpen(false)}
            className="md:hidden flex items-center justify-center w-11 h-11 -mr-2 text-[var(--foreground)]"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {user?.role === "super_admin" && organizations.length > 1 && (
          <div className="p-4 border-b border-[var(--border)]">
            <label className="block text-xs font-bold uppercase text-[var(--muted)] mb-1">Salão ativo</label>
            <select
              value={organizationId || ""}
              onChange={(e) => setSelectedOrgId(e.target.value)}
              className="w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface)] text-[var(--foreground)] px-2 py-1 font-mono text-xs focus:outline-none focus:border-[var(--accent)]"
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
              <Link key={item.path} to={item.path} onClick={() => setNavOpen(false)}>
                <span className={`flex items-center gap-3 px-3 py-3 rounded-[var(--radius-md)] border text-sm font-bold uppercase tracking-wide transition-all ${isActive ? "border-transparent bg-[image:var(--grad)] text-white glow-accent" : "border-[var(--border)] bg-[var(--surface-glass)] text-[var(--foreground)] hover:border-[var(--accent)] hover:-translate-y-0.5"}`}>
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </span>
              </Link>
            )
          })}
        </nav>

        <div className="p-4 pb-[calc(1rem+env(safe-area-inset-bottom))] border-t border-[var(--border)]">
          <div className="mb-4 px-3">
            <p className="text-sm font-medium truncate">{user?.username}</p>
            <p className="text-xs text-[var(--muted)]">{roleLabel}</p>
          </div>
          <div className="space-y-1">
            <div className="px-3 pb-2 font-mono text-[10px] text-[var(--muted)] space-x-2">
              <a
                href={`${import.meta.env.VITE_LANDING_URL || "https://www.gaussix.com"}/privacidade`}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-[var(--accent)]"
              >
                Privacidade
              </a>
              <a
                href={`${import.meta.env.VITE_LANDING_URL || "https://www.gaussix.com"}/termos`}
                target="_blank"
                rel="noopener noreferrer"
                className="underline hover:text-[var(--accent)]"
              >
                Termos
              </a>
            </div>
            {user?.role === "super_admin" && (
              <Link to="/admin/observability">
                <button className={`w-full flex items-center justify-start gap-3 px-3 py-2 text-sm font-bold uppercase transition-colors ${location.pathname === "/admin/observability" ? "text-[var(--accent)]" : "text-[var(--muted)] hover:text-[var(--accent)]"}`}>
                  <Activity className="w-4 h-4" /> Observabilidade (plataforma)
                </button>
              </Link>
            )}
            {isDev && user?.role === "super_admin" && (
              <Link to="/admin/data-lake">
                <button className={`w-full flex items-center justify-start gap-3 px-3 py-2 text-sm font-bold uppercase transition-colors ${location.pathname === "/admin/data-lake" ? "text-[var(--accent)]" : "text-[var(--muted)] hover:text-[var(--accent)]"}`}>
                  <Database className="w-4 h-4" /> Data Lake (dev)
                </button>
              </Link>
            )}
            <button
              onClick={signOut}
              className="flex items-center gap-3 px-3 py-3 w-full rounded-[var(--radius-md)] border border-[var(--border)] bg-[var(--surface-glass)] text-[var(--foreground)] text-sm font-bold uppercase tracking-wide transition-all hover:border-[var(--danger)] hover:text-[var(--danger)] hover:-translate-y-0.5"
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
    </div>
  )
}
