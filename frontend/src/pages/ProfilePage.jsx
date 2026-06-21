import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts'
import AppShell from '../components/ui/AppShell'
import api from '../utils/api'

function StatCard({ label, value, sub, color = 'text-white' }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
      <p className="text-gray-500 text-xs">{label}</p>
      <p className={`text-2xl font-bold mt-1 ${color}`}>{value}</p>
      {sub && <p className="text-gray-600 text-xs mt-1">{sub}</p>}
    </div>
  )
}

export default function ProfilePage() {
  const { data, isLoading } = useQuery({
    queryKey: ['user-stats'],
    queryFn: () => api.get('/query/stats').then(r => r.data),
  })

  if (isLoading) {
    return (
      <AppShell>
        <div className="p-6 flex items-center justify-center h-full">
          <div className="text-gray-500">Loading profile...</div>
        </div>
      </AppShell>
    )
  }

  const { user, stats, activity } = data || {}

  const memberSince = user?.member_since
    ? new Date(user.member_since).toLocaleDateString('en-US', { year: 'numeric', month: 'long' })
    : '—'

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto space-y-6">
        {/* Profile header */}
        <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-blue-600 flex items-center justify-center text-2xl font-bold text-white">
            {user?.email?.[0]?.toUpperCase() || 'U'}
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-white">{user?.username || 'User'}</h1>
            <p className="text-gray-500 text-sm">{user?.email}</p>
            <div className="flex items-center gap-3 mt-2">
              <span className="text-xs bg-blue-950 border border-blue-800 text-blue-400 px-2 py-0.5 rounded-full capitalize">
                {user?.plan || 'free'} plan
              </span>
              <span className="text-xs text-gray-600">Member since {memberSince}</span>
            </div>
          </div>
        </div>

        {/* Stats grid */}
        <div>
          <h2 className="text-white font-semibold mb-3">Usage Overview</h2>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <StatCard label="Total Queries" value={stats?.total_queries ?? 0} />
            <StatCard
              label="Success Rate"
              value={`${stats?.success_rate ?? 0}%`}
              color={stats?.success_rate >= 80 ? 'text-green-400' : 'text-yellow-400'}
            />
            <StatCard label="Active Connections" value={stats?.active_connections ?? 0} />
            <StatCard label="Successful Queries" value={stats?.successful_queries ?? 0} color="text-green-400" />
            <StatCard
              label="Guardrail Blocks"
              value={stats?.guardrail_blocks ?? 0}
              color={stats?.guardrail_blocks > 0 ? 'text-orange-400' : 'text-white'}
              sub="Blocked queries"
            />
            <StatCard
              label="Tokens Used"
              value={stats?.total_tokens_used?.toLocaleString() ?? 0}
              sub="All time"
            />
          </div>
        </div>

        {/* Performance */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">Avg Query Time</p>
            <p className="text-3xl font-bold text-white">{stats?.avg_execution_ms ?? 0}<span className="text-gray-500 text-base font-normal ml-1">ms</span></p>
            <p className="text-gray-600 text-xs mt-1">Per successful query</p>
          </div>
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-3">Failed Queries</p>
            <p className="text-3xl font-bold text-white">
              {(stats?.total_queries ?? 0) - (stats?.successful_queries ?? 0) - (stats?.guardrail_blocks ?? 0)}
            </p>
            <p className="text-gray-600 text-xs mt-1">Generation or execution errors</p>
          </div>
        </div>

        {/* Activity chart */}
        {activity && activity.length > 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-4">Last 7 Days Activity</p>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={activity} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#2a2a38" />
                  <XAxis
                    dataKey="date"
                    tick={{ fill: '#6b7280', fontSize: 10 }}
                    tickFormatter={d => d.slice(5)}
                  />
                  <YAxis tick={{ fill: '#6b7280', fontSize: 10 }} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1a1a24', border: '1px solid #2a2a38', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: '#9b9bb0' }}
                    itemStyle={{ color: '#3b82f6' }}
                  />
                  <Bar dataKey="count" fill="#3b82f6" radius={[3, 3, 0, 0]} name="Queries" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {activity?.length === 0 && (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-6 text-center">
            <p className="text-gray-500 text-sm">No activity in the last 7 days. Start by running a query!</p>
          </div>
        )}
      </div>
    </AppShell>
  )
}
