import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"

/** Rotas de gestão do salão (clientes, catálogo) — bloqueadas para role professional. */
export function OrgAdminRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="p-8 font-mono">Carregando...</div>
  }

  if (user?.role === "professional") {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
