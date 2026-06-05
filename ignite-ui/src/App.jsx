import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './store'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Distributors from './pages/Distributors'
import TreeView from './pages/TreeView'
import Cycles from './pages/Cycles'
import CommissionReport from './pages/CommissionReport'
import Compliance from './pages/Compliance'
import Config from './pages/Config'

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="flex items-center justify-center h-screen text-gray-500">Loading…</div>
  return user ? children : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          <Route path="/" element={<Protected><Layout /></Protected>}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<Dashboard />} />
            <Route path="distributors" element={<Distributors />} />
            <Route path="tree" element={<TreeView />} />
            <Route path="cycles" element={<Cycles />} />
            <Route path="commissions/:cycleId?" element={<CommissionReport />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="config" element={<Config />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
