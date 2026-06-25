import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import AppShell from '../components/ui/AppShell'
import ResultChart from '../components/charts/ResultChart'
import ResultsTable from '../components/editor/ResultsTable'
import api from '../utils/api'

function NumberWidget({ widget }) {
  const value = widget.rows?.[0]?.[0]
  const formatted = typeof value === 'number'
    ? value.toLocaleString()
    : value ?? '—'

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-6 flex flex-col justify-between h-full">
      <div>
        <p className="text-gray-500 text-xs uppercase tracking-wider mb-1">{widget.title}</p>
        <p className="text-4xl font-bold text-white mt-2">{formatted}</p>
      </div>
      <p className="text-gray-600 text-xs mt-3 leading-relaxed">{widget.description}</p>
    </div>
  )
}

function ChartWidget({ widget }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl p-5 h-full">
      <p className="text-white font-semibold text-sm mb-1">{widget.title}</p>
      <p className="text-gray-600 text-xs mb-4">{widget.description}</p>
      {widget.rows?.length > 0 ? (
        <ResultChart columns={widget.columns} rows={widget.rows} />
      ) : (
        <div className="h-48 flex items-center justify-center text-gray-600 text-sm">No data</div>
      )}
    </div>
  )
}

function TableWidget({ widget }) {
  return (
    <div className="bg-gray-900 border border-gray-800 rounded-2xl overflow-hidden h-full">
      <div className="px-5 py-4 border-b border-gray-800">
        <p className="text-white font-semibold text-sm">{widget.title}</p>
        <p className="text-gray-600 text-xs mt-0.5">{widget.description}</p>
      </div>
      {widget.rows?.length > 0
        ? <ResultsTable columns={widget.columns} rows={widget.rows} />
        : <div className="p-6 text-center text-gray-600 text-sm">No data</div>
      }
    </div>
  )
}

function Widget({ widget }) {
  if (widget.error) {
    return (
      <div className="bg-gray-900 border border-red-900/50 rounded-2xl p-5">
        <p className="text-gray-400 text-sm font-medium mb-1">{widget.title}</p>
        <p className="text-red-400 text-xs font-mono">{widget.error}</p>
      </div>
    )
  }

  if (widget.chart_type === 'number') return <NumberWidget widget={widget} />
  if (widget.chart_type === 'table') return <TableWidget widget={widget} />
  return <ChartWidget widget={widget} />
}

export default function DashboardBuilderPage() {
  const [selectedConn, setSelectedConn] = useState('')
  const [request, setRequest] = useState('')
  const [dashboard, setDashboard] = useState(null)

  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const buildMutation = useMutation({
    mutationFn: (data) => api.post('/dashboard/generate', data).then(r => r.data),
    onSuccess: setDashboard,
  })

  const handleBuild = () => {
    if (!request.trim() || !selectedConn) return
    setDashboard(null)
    buildMutation.mutate({ connection_id: selectedConn, request })
  }

  const EXAMPLES = [
    "Give me a complete sales overview",
    "Show customer analysis dashboard",
    "Revenue and orders summary",
    "Product performance overview",
  ]

  // Layout: number widgets first row, then charts, then table
  const numberWidgets = dashboard?.widgets?.filter(w => w.chart_type === 'number') || []
  const chartWidgets = dashboard?.widgets?.filter(w => ['bar','line','pie'].includes(w.chart_type)) || []
  const tableWidgets = dashboard?.widgets?.filter(w => w.chart_type === 'table') || []

  return (
    <AppShell>
      <div className="p-6 max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6">
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-xl font-bold text-white">Dashboard Builder</h1>
            <span className="text-xs bg-purple-600/20 border border-purple-600/30 text-purple-400 px-2 py-0.5 rounded-full">
              UNIQUE
            </span>
          </div>
          <p className="text-gray-500 text-sm">
            One sentence → complete BI dashboard. No configuration needed.
          </p>
        </div>

        {/* Builder form */}
        <div className="bg-gray-900 border border-gray-700 rounded-2xl p-5 mb-6">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="flex-1 min-w-48">
              <label className="block text-xs text-gray-400 mb-1.5">Database</label>
              <select value={selectedConn} onChange={e => { setSelectedConn(e.target.value); setDashboard(null) }}
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500">
                <option value="">Select database...</option>
                {connections.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.db_type === 'sqlite' ? '📁' : c.db_type === 'mysql' ? '🐬' : '🐘'} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="flex-[2] min-w-64">
              <label className="block text-xs text-gray-400 mb-1.5">What do you want to see?</label>
              <input value={request} onChange={e => setRequest(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleBuild() }}
                placeholder="e.g. Give me a complete sales overview"
                className="w-full bg-gray-800 border border-gray-700 rounded-xl px-4 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
            </div>
            <button onClick={handleBuild}
              disabled={!request.trim() || !selectedConn || buildMutation.isPending}
              className="bg-purple-600 hover:bg-purple-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-xl text-sm font-medium transition-colors whitespace-nowrap">
              {buildMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Building...
                </span>
              ) : '✨ Build Dashboard'}
            </button>
          </div>

          {/* Examples */}
          {!dashboard && !buildMutation.isPending && (
            <div className="mt-4 flex flex-wrap gap-2">
              <span className="text-xs text-gray-600">Try:</span>
              {EXAMPLES.map(ex => (
                <button key={ex} onClick={() => setRequest(ex)}
                  className="text-xs text-gray-500 hover:text-blue-400 bg-gray-800 hover:bg-gray-750 border border-gray-700 rounded-lg px-3 py-1 transition-colors">
                  {ex}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Loading */}
        {buildMutation.isPending && (
          <div className="text-center py-20">
            <div className="relative w-16 h-16 mx-auto mb-6">
              <div className="w-16 h-16 border-2 border-gray-800 rounded-full" />
              <div className="absolute inset-0 w-16 h-16 border-2 border-t-purple-500 rounded-full animate-spin" />
            </div>
            <p className="text-white font-medium text-lg">Building your dashboard...</p>
            <p className="text-gray-500 text-sm mt-1">Generating and executing queries in parallel</p>
            <div className="flex justify-center gap-2 mt-4">
              {['Planning widgets', 'Executing queries', 'Rendering charts'].map((s, i) => (
                <span key={s} className="text-xs text-gray-600 bg-gray-900 border border-gray-800 rounded-full px-3 py-1">
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Error */}
        {buildMutation.isError && (
          <div className="bg-red-950/50 border border-red-800 rounded-2xl p-5">
            <p className="text-red-400">{buildMutation.error?.response?.data?.detail || 'Dashboard generation failed'}</p>
          </div>
        )}

        {/* Dashboard */}
        {dashboard && !buildMutation.isPending && (
          <div className="space-y-4">
            {/* Dashboard header */}
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-white font-bold text-xl">{dashboard.title}</h2>
                <p className="text-gray-500 text-sm mt-0.5">{dashboard.description}</p>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-600">
                  {dashboard.widgets?.length} widgets · {(dashboard.generated_in_ms / 1000).toFixed(1)}s
                </span>
                <Link to={`/query/${selectedConn}`}
                  className="text-xs text-blue-400 hover:text-blue-300 border border-blue-800/50 rounded-lg px-3 py-1.5 transition-colors">
                  Query this DB →
                </Link>
              </div>
            </div>

            {/* KPI row */}
            {numberWidgets.length > 0 && (
              <div className={`grid gap-4 ${numberWidgets.length === 1 ? 'grid-cols-1' : numberWidgets.length === 2 ? 'grid-cols-2' : numberWidgets.length === 3 ? 'grid-cols-3' : 'grid-cols-4'}`}>
                {numberWidgets.map((w, i) => <Widget key={i} widget={w} />)}
              </div>
            )}

            {/* Charts row */}
            {chartWidgets.length > 0 && (
              <div className={`grid gap-4 ${chartWidgets.length === 1 ? 'grid-cols-1' : 'grid-cols-2'}`}>
                {chartWidgets.map((w, i) => <Widget key={i} widget={w} />)}
              </div>
            )}

            {/* Table row */}
            {tableWidgets.length > 0 && (
              <div>
                {tableWidgets.map((w, i) => <Widget key={i} widget={w} />)}
              </div>
            )}
          </div>
        )}

        {!connections.length && (
          <div className="text-center py-16">
            <p className="text-4xl mb-3">🔌</p>
            <p className="text-gray-400 font-medium">No databases connected</p>
            <Link to="/connections" className="text-blue-400 text-sm mt-2 inline-block hover:text-blue-300">
              Add a database →
            </Link>
          </div>
        )}
      </div>
    </AppShell>
  )
}
