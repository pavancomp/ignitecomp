import { Outlet, NavLink, useNavigate } from 'react-router-dom'
import { useAuth } from '../store'

const nav = [
  { to: '/dashboard',    label: 'Dashboard',   icon: '▦' },
  { to: '/distributors', label: 'BAs',         icon: '👤' },
  { to: '/tree',         label: 'Tree',         icon: '🌿' },
  { to: '/cycles',       label: 'Cycles',       icon: '🔄' },
  { to: '/commissions',  label: 'Commissions',  icon: '₹' },
  { to: '/compliance',   label: 'Compliance',   icon: '📋' },
  { to: '/config',       label: 'Config',       icon: '⚙' },
]

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const handleLogout = () => { logout(); navigate('/login') }

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-56 bg-indigo-900 text-white flex flex-col">
        <div className="px-4 py-5 border-b border-indigo-800">
          <h1 className="text-lg font-bold tracking-tight">Ignite Engine</h1>
          <p className="text-xs text-indigo-300 mt-0.5">India · INR only</p>
        </div>

        <nav className="flex-1 py-4 space-y-0.5">
          {nav.map(({ to, label, icon }) => (
            <NavLink
              key={to} to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-2.5 text-sm transition-colors ${isActive ? 'bg-indigo-700 text-white font-medium' : 'text-indigo-200 hover:bg-indigo-800 hover:text-white'}`
              }
            >
              <span className="text-base w-5 text-center">{icon}</span>
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="px-4 py-4 border-t border-indigo-800">
          <div className="text-xs text-indigo-300 mb-2">
            <span className="font-medium text-white">{user?.username}</span>
            <span className="ml-1.5 px-1.5 py-0.5 rounded bg-indigo-700 text-indigo-200">{user?.role}</span>
          </div>
          <button onClick={handleLogout} className="text-xs text-indigo-300 hover:text-white transition-colors">
            Sign out
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  )
}
