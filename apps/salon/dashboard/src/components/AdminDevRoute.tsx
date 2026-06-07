import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"

/** Rotas de plataforma visíveis só em DEV para super_admin. */
export function AdminDevRoute() {
  const { user, isLoading } = useAuth()

  if (isLoading) {
    return <div className="p-8 font-mono">Carregando...</div>
  }

  if (!import.meta.env.DEV || user?.role !== "super_admin") {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}
