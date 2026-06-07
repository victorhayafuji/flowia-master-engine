/* eslint-disable react-refresh/only-export-components */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react"
import { api } from "@/shared/lib/api"

const SALON_DEFAULT_ORG = "22222222-2222-2222-2222-222222222222"
const ORG_STORAGE_KEY = "flowia_selected_org_id"

interface User {
  username: string
  role: string
  organization_id?: string
  organization_name?: string
  professional_id?: string
}

interface Organization {
  id: string
  name: string
  slug?: string
  vertical?: string
}

interface AuthContextType {
  user: User | null
  isLoading: boolean
  signOut: () => Promise<void>
  loginWithCredentials: (username: string, password: string) => Promise<void>
  devLogin?: () => Promise<{ error: Error | null }>
  devSalonLogin?: () => Promise<{ error: Error | null }>
  session: { user: User } | null
  organizationId: string | undefined
  organizationName: string | undefined
  orgHeader: Record<string, string>
  organizations: Organization[]
  setSelectedOrgId: (orgId: string) => void
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isLoading: true,
  signOut: async () => {},
  loginWithCredentials: async () => {},
  session: null,
  organizationId: undefined,
  organizationName: undefined,
  orgHeader: {},
  organizations: [],
  setSelectedOrgId: () => {},
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [organizations, setOrganizations] = useState<Organization[]>([])
  const [selectedOrgId, setSelectedOrgIdState] = useState<string | null>(
    () => localStorage.getItem(ORG_STORAGE_KEY)
  )

  const setSelectedOrgId = useCallback((orgId: string) => {
    setSelectedOrgIdState(orgId)
    localStorage.setItem(ORG_STORAGE_KEY, orgId)
  }, [])

  const loadUser = useCallback(async () => {
    const data = await api.get("/auth/me")
    if (data.status === "success" && data.user) {
      setUser(data.user)
      if (data.user.role === "super_admin") {
        try {
          const orgRes = await api.get("/organizations/")
          const list = (orgRes.data || []).filter(
            (o: Organization) => !o.vertical || o.vertical === "salon"
          )
          setOrganizations(list)
          if (!selectedOrgId && list.length > 0) {
            const salon = list.find((o: Organization) => o.id === SALON_DEFAULT_ORG)
            setSelectedOrgId(salon?.id || list[0].id)
          }
        } catch {
          setOrganizations([])
        }
      }
    } else {
      setUser(null)
    }
  }, [selectedOrgId, setSelectedOrgId])

  useEffect(() => {
    const checkSession = async () => {
      try {
        await loadUser()
      } catch {
        setUser(null)
      } finally {
        setIsLoading(false)
      }
    }

    checkSession()
  }, [loadUser])

  const organizationId = useMemo(() => {
    if (!user) return undefined
    if (user.role === "super_admin") {
      return selectedOrgId || SALON_DEFAULT_ORG
    }
    return user.organization_id
  }, [user, selectedOrgId])

  const organizationName = useMemo(() => {
    if (!user) return undefined
    if (user.role === "super_admin") {
      const org = organizations.find((o) => o.id === organizationId)
      return org?.name || "Salão"
    }
    return user.organization_name || "Salão"
  }, [user, organizations, organizationId])

  const orgHeader = useMemo((): Record<string, string> => {
    if (!organizationId) return {}
    return { "x-organization-id": organizationId }
  }, [organizationId])

  const devLoginWith = (email: string | undefined, password: string | undefined, label: string) =>
    async () => {
      if (!email || !password) {
        return { error: new Error(`Configure ${label} no .env da raiz`) }
      }

      setIsLoading(true)
      try {
        const data = await api.post("/auth/login", { username: email, password })
        if (data.status === "success") {
          await loadUser()
          return { error: null }
        }
        return { error: new Error("Falha no login de desenvolvimento") }
      } catch (err) {
        const message = err instanceof Error ? err.message : "Erro de autenticação"
        return { error: new Error(message) }
      } finally {
        setIsLoading(false)
      }
    }

  const devLogin = import.meta.env.DEV
    ? devLoginWith(import.meta.env.VITE_DEV_EMAIL, import.meta.env.VITE_DEV_PASSWORD, "VITE_DEV_EMAIL e VITE_DEV_PASSWORD")
    : undefined

  const devSalonLogin = import.meta.env.DEV
    ? devLoginWith(import.meta.env.VITE_DEV_SALON_EMAIL, import.meta.env.VITE_DEV_SALON_PASSWORD, "VITE_DEV_SALON_EMAIL e VITE_DEV_SALON_PASSWORD")
    : undefined

  const signOut = async () => {
    try {
      await api.post("/auth/logout", {})
      setUser(null)
    } catch (err) {
      console.error("Erro ao fazer logout", err)
    }
  }

  const loginWithCredentials = async (username: string, password: string) => {
    const data = await api.post("/auth/login", { username, password })
    if (data.status !== "success") {
      throw new Error("Falha no login")
    }
    await loadUser()
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        signOut,
        loginWithCredentials,
        devLogin,
        devSalonLogin,
        session: user ? { user } : null,
        organizationId,
        organizationName,
        orgHeader,
        organizations,
        setSelectedOrgId,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
