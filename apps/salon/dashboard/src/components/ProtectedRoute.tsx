import { Navigate, Outlet } from "react-router-dom"
import { useAuth } from "@/features/auth/AuthContext"

export function ProtectedRoute() {
  const { session, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--background)]">
        <div className="animate-spin rounded-none h-10 w-10 border-4 border-[var(--border)] border-t-[var(--accent)]"></div>
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
