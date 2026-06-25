import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'

const NAV = [
  { path: '/dashboard', icon: '⚡', label: 'Dashboard' },
  { path: '/query', icon: '💬', label: 'Query' },
  { path: '/builder', icon: '✨', label: 'Dashboard Builder', badge: 'NEW' },
  { path: '/insights', icon: '🔍', label: 'Insights' },
  { path: '/connections', icon: '🔌', label: 'Connections' },
  { path: '/optimizer', icon: '🔧', label: 'Optimizer' },
  { path: '/history', icon: '📋', label: 'History' },
]

export default function AppShell({ children }) {
  const { pathname } = useLocation()
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()

  const handleLogout = async () => { await logout(); navigate('/') }

  return (
    <div className="flex h-screen bg-gray-950 overflow-hidden">
      <aside className="w-56 flex flex-col border-r border-gray-800 bg-gray-900/50 shrink-0">
        {/* Logo */}
        <div className="px-4 py-5 border-b border-gray-800">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center text-xs font-bold">S</div>
            <span className="font-bold text-white">SQL<span className="text-blue-400">Mind</span></span>
          </Link>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-2 py-3 space-y-0.5 overflow-y-auto">
          {NAV.map(({ path, icon, label, badge }) => {
            const active = pathname === path || pathname.startsWith(path + '/')
            return (
              <Link key={path} to={path}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm transition-all
                  ${active
                    ? 'bg-blue-600 text-white shadow-lg shadow-blue-600/20'
                    : 'text-gray-400 hover:text-white hover:bg-gray-800/70'}`}>
                <span className="text-base shrink-0">{icon}</span>
                <span className="flex-1">{label}</span>
                {badge && (
                  <span className="text-xs bg-purple-600/30 text-purple-400 border border-purple-600/30 px-1.5 py-0.5 rounded-full leading-none">
                    {badge}
                  </span>
                )}
              </Link>
            )
          })}
        </nav>

        {/* User */}
        <div className="px-3 py-3 border-t border-gray-800">
          <Link to="/profile"
            className={`flex items-center gap-3 px-2 py-2 rounded-xl hover:bg-gray-800/70 transition-colors
              ${pathname === '/profile' ? 'bg-gray-800' : ''}`}>
            <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-bold text-white shrink-0">
              {user?.email?.[0]?.toUpperCase() || 'U'}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-white truncate font-medium">{user?.email}</p>
              <p className="text-xs text-gray-600">Free plan</p>
            </div>
          </Link>
          <button onClick={handleLogout}
            className="w-full mt-1 text-xs text-gray-600 hover:text-red-400 transition-colors text-left px-2 py-1 rounded-lg hover:bg-gray-800/50">
            Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto bg-gray-950">{children}</main>
    </div>
  )
}
