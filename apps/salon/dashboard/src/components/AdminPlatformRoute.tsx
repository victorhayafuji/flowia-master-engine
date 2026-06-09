import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"

/** Rotas de plataforma Gaussix — super_admin em dev e prod. */
export function AdminPlatformRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="p-8 font-mono">Carregando...</div>
  }

  if (user?.role !== "super_admin") {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
