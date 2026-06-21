import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import AppShell from '../components/ui/AppShell'
import api from '../utils/api'

function StatCard({ label, value, sub }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-gray-500 text-xs">{label}</p>
      <p className="text-white text-2xl font-bold mt-1">{value}</p>
      {sub && <p className="text-gray-600 text-xs mt-1">{sub}</p>}
    </div>
  )
}

export default function DashboardPage() {
  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const { data: history = [] } = useQuery({
    queryKey: ['history'],
    queryFn: () => api.get('/query/history?limit=5').then(r => r.data),
  })

  const successCount = history.filter(q => q.status === 'success').length
  const blockedCount = history.filter(q => q.guardrail_triggered).length

  return (
    <AppShell>
      <div className="p-6 max-w-5xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white">Dashboard</h1>
          <p className="text-gray-500 text-sm mt-1">Your SQL intelligence overview</p>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Connections" value={connections.length} sub="Active DBs" />
          <StatCard label="Queries (recent)" value={history.length} sub="Last 5" />
          <StatCard label="Success rate" value={history.length ? `${Math.round(successCount/history.length*100)}%` : '—'} />
          <StatCard label="Guardrail blocks" value={blockedCount} sub="Blocked queries" />
        </div>

        {/* Quick actions */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <Link to="/query" className="group bg-blue-600 hover:bg-blue-500 rounded-xl p-5 transition-colors">
            <div className="text-2xl mb-2">💬</div>
            <h3 className="text-white font-semibold">New Query</h3>
            <p className="text-blue-200 text-sm mt-1">Ask your database in plain English</p>
          </Link>
          <Link to="/connections" className="group bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl p-5 transition-colors">
            <div className="text-2xl mb-2">🔌</div>
            <h3 className="text-white font-semibold">Add Connection</h3>
            <p className="text-gray-500 text-sm mt-1">Connect PostgreSQL, MySQL, SQLite</p>
          </Link>
        </div>

        {/* Connections list */}
        <div className="mb-8">
          <h2 className="text-white font-semibold mb-3">Your Databases</h2>
          {connections.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-8 text-center">
              <p className="text-gray-500 text-sm">No connections yet.</p>
              <Link to="/connections" className="text-blue-400 text-sm mt-2 inline-block hover:text-blue-300">
                Add your first database →
              </Link>
            </div>
          ) : (
            <div className="space-y-2">
              {connections.map(conn => (
                <Link
                  key={conn.id}
                  to={`/query/${conn.id}`}
                  className="flex items-center gap-4 bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl px-4 py-3 transition-colors"
                >
                  <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-sm">
                    {conn.db_type === 'postgres' ? '🐘' : conn.db_type === 'mysql' ? '🐬' : '📁'}
                  </div>
                  <div className="flex-1">
                    <p className="text-white text-sm font-medium">{conn.name}</p>
                    <p className="text-gray-500 text-xs">{conn.db_type}</p>
                  </div>
                  <span className="text-gray-600 text-xs">Query →</span>
                </Link>
              ))}
            </div>
          )}
        </div>

        {/* Recent history */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-white font-semibold">Recent Queries</h2>
            <Link to="/history" className="text-blue-400 text-xs hover:text-blue-300">View all →</Link>
          </div>
          {history.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
              <p className="text-gray-500 text-sm">No queries yet. Start by asking your database something.</p>
            </div>
          ) : (
            <div className="space-y-2">
              {history.map(q => (
                <div key={q.id} className="bg-gray-900 border border-gray-800 rounded-xl px-4 py-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      q.status === 'success' ? 'bg-green-400' :
                      q.guardrail_triggered ? 'bg-orange-400' : 'bg-red-400'
                    }`} />
                    <p className="text-white text-sm truncate flex-1">{q.natural_language}</p>
                    <span className="text-gray-600 text-xs shrink-0">
                      {q.execution_time_ms ? `${Math.round(q.execution_time_ms)}ms` : ''}
                    </span>
                  </div>
                  {q.generated_sql && (
                    <p className="text-gray-600 text-xs font-mono truncate pl-3.5">{q.generated_sql}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}
