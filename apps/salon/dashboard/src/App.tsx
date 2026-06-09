import { Suspense, lazy } from "react"
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom"
import { AuthProvider } from "@/features/auth/AuthContext"
import { ProtectedRoute } from "./components/ProtectedRoute"
import { AdminDevRoute } from "./components/AdminDevRoute"
import { AdminPlatformRoute } from "./components/AdminPlatformRoute"
import { OrgAdminRoute } from "./components/OrgAdminRoute"
import { Layout } from "./components/Layout"
import { Login } from "./pages/Login"

const Overview = lazy(() => import("./pages/Overview").then(m => ({ default: m.Overview })))
const Agenda = lazy(() => import("./pages/Agenda").then(m => ({ default: m.Agenda })))
const Catalog = lazy(() => import("./pages/Catalog").then(m => ({ default: m.Catalog })))
const Patients = lazy(() => import("./pages/Patients").then(m => ({ default: m.Patients })))
const DataLake = lazy(() => import("./pages/DataLake").then(m => ({ default: m.DataLake })))
const ChatTest = lazy(() => import("./pages/ChatTest").then(m => ({ default: m.ChatTest })))
const AgentObservability = lazy(() =>
  import("./pages/AgentObservability").then(m => ({ default: m.AgentObservability }))
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
                <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                  <Overview />
                </Suspense>
              } />
              <Route path="/agenda" element={
                <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                  <Agenda />
                </Suspense>
              } />
              <Route element={<OrgAdminRoute />}>
                <Route path="/patients" element={
                  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                    <Patients />
                  </Suspense>
                } />
                <Route path="/catalog" element={
                  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                    <Catalog />
                  </Suspense>
                } />
              </Route>
              <Route path="/data-lake" element={<Navigate to="/admin/data-lake" replace />} />
              <Route path="/chat-test" element={<Navigate to="/admin/chat-test" replace />} />

              <Route element={<AdminPlatformRoute />}>
                <Route path="/admin/observability" element={
                  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                    <AgentObservability />
                  </Suspense>
                } />
              </Route>

              <Route element={<AdminDevRoute />}>
                <Route path="/admin/data-lake" element={
                  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
                    <DataLake />
                  </Suspense>
                } />
                <Route path="/admin/chat-test" element={
                  <Suspense fallback={<div className="p-8 font-mono">Carregando...</div>}>
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
