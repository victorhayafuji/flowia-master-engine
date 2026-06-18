import { Suspense, lazy } from "react"
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider } from "@/features/auth/AuthContext"
import { ProtectedRoute } from "./components/ProtectedRoute"
import { AdminDevRoute } from "./components/AdminDevRoute"
import { AdminPlatformRoute } from "./components/AdminPlatformRoute"
import { OrgAdminRoute } from "./components/OrgAdminRoute"
import { Layout } from "./components/Layout"
import { PageFallback } from "./components/PageFallback"
import { Login } from "@/features/auth/Login"

const Overview = lazy(() => import("@/features/overview/Overview").then(m => ({ default: m.Overview })))
const Agenda = lazy(() => import("@/features/agenda/Agenda").then(m => ({ default: m.Agenda })))
const Catalog = lazy(() => import("@/features/catalog/Catalog").then(m => ({ default: m.Catalog })))
const Patients = lazy(() => import("@/features/clients/Patients").then(m => ({ default: m.Patients })))
const Settings = lazy(() => import("@/features/settings/Settings").then(m => ({ default: m.Settings })))
const DataLake = lazy(() => import("@/features/admin/DataLake").then(m => ({ default: m.DataLake })))
const ChatTest = lazy(() => import("@/features/admin/ChatTest").then(m => ({ default: m.ChatTest })))
const AgentObservability = lazy(() =>
  import("@/features/admin/AgentObservability").then(m => ({ default: m.AgentObservability }))
)

function App() {
  return (
    <AuthProvider>
      <Router>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route element={<ProtectedRoute />}>
            <Route element={<Layout />}>
              <Route path="/" element={
                <Suspense fallback={<PageFallback />}>
                  <Overview />
                </Suspense>
              } />
              <Route path="/agenda" element={
                <Suspense fallback={<PageFallback />}>
                  <Agenda />
                </Suspense>
              } />
              <Route element={<OrgAdminRoute />}>
                <Route path="/patients" element={
                  <Suspense fallback={<PageFallback />}>
                    <Patients />
                  </Suspense>
                } />
                <Route path="/catalog" element={
                  <Suspense fallback={<PageFallback />}>
                    <Catalog />
                  </Suspense>
                } />
                <Route path="/settings" element={
                  <Suspense fallback={<PageFallback />}>
                    <Settings />
                  </Suspense>
                } />
              </Route>
              <Route path="/data-lake" element={<Navigate to="/admin/data-lake" replace />} />
              <Route path="/chat-test" element={<Navigate to="/admin/chat-test" replace />} />

              <Route element={<AdminPlatformRoute />}>
                <Route path="/admin/observability" element={
                  <Suspense fallback={<PageFallback />}>
                    <AgentObservability />
                  </Suspense>
                } />
              </Route>

              <Route element={<AdminDevRoute />}>
                <Route path="/admin/data-lake" element={
                  <Suspense fallback={<PageFallback />}>
                    <DataLake />
                  </Suspense>
                } />
                <Route path="/admin/chat-test" element={
                  <Suspense fallback={<PageFallback />}>
                    <ChatTest />
                  </Suspense>
                } />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Router>
    </AuthProvider>
  )
}

export default App
