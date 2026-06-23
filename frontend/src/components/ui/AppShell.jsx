import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

const NAV = [
  { path: '/dashboard', icon: '⚡', label: 'Dashboard' },
  { path: '/query', icon: '💬', label: 'Query' },
  { path: '/insights', icon: '✨', label: 'Insights' },
  { path: '/connections', icon: '🔌', label: 'Connections' },
  { path: '/optimizer', icon: '🔧', label: 'Optimizer' },
  { path: '/history', icon: '📋', label: 'History' },
]

export default function AppShell({ children }) {
  const { pathname } = useLocation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => { await logout(); navigate('/login') }

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <aside className="w-56 flex flex-col border-r border-gray-800 bg-gray-900 shrink-0">
        <div className="px-4 py-5 border-b border-gray-800">
          <h1 className="text-white font-bold text-lg tracking-tight">
            SQL<span className="text-blue-400">Mind</span>
          </h1>
          <p className="text-gray-500 text-xs mt-0.5">AI Data Intelligence</p>
        </div>

        <nav className="flex-1 px-2 py-4 space-y-0.5">
          {NAV.map(({ path, icon, label }) => {
            const active = pathname === path || pathname.startsWith(path + '/')
            return (
              <Link key={path} to={path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors
                  ${active ? 'bg-blue-600 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}>
                <span className="text-base">{icon}</span>{label}
              </Link>
            )
          })}
        </nav>

        <div className="px-3 py-4 border-t border-gray-800">
          <Link to="/profile"
            className={`flex items-center gap-3 px-2 py-2 rounded-lg hover:bg-gray-800 transition-colors
              ${pathname === '/profile' ? 'bg-gray-800' : ''}`}>
            <div className="w-7 h-7 rounded-full bg-blue-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
              {user?.email?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white truncate">{user?.email}</p>
              <p className="text-xs text-gray-500">View profile</p>
            </div>
          </Link>
          <button onClick={handleLogout}
            className="w-full mt-1.5 text-xs text-gray-500 hover:text-red-400 transition-colors text-left px-2 py-1">
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto">{children}</main>
    </div>
  )
}
