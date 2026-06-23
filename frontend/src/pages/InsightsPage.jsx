import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import AppShell from '../components/ui/AppShell'
import ResultChart from '../components/charts/ResultChart'
import api from '../utils/api'

const SEVERITY_STYLE = {
  critical: 'border-red-800 bg-red-950/40',
  warning: 'border-yellow-800 bg-yellow-950/40',
  info: 'border-gray-700 bg-gray-900',
}

const TYPE_ICON = {
  summary: '📊',
  anomaly: '⚠️',
  trend: '📈',
  top_values: '🏆',
  quality: '🔍',
}

function InsightCard({ insight }) {
  const [showChart, setShowChart] = useState(false)
  const style = SEVERITY_STYLE[insight.severity] || SEVERITY_STYLE.info

  return (
    <div className={`border rounded-xl p-4 transition-all ${style}`}>
      <div className="flex items-start gap-3">
        <span className="text-xl shrink-0">{TYPE_ICON[insight.type] || '💡'}</span>
        <div className="flex-1 min-w-0">
          <p className="text-gray-400 text-xs mb-0.5">{insight.title}</p>
          <p className="text-white font-semibold text-sm">{insight.value}</p>
          <p className="text-gray-500 text-xs mt-1 leading-relaxed">{insight.detail}</p>

          {insight.data?.labels && insight.data?.values && (
            <button onClick={() => setShowChart(p => !p)}
              className="text-xs text-blue-400 hover:text-blue-300 mt-2 transition-colors">
              {showChart ? '▼ Hide chart' : '▶ Show chart'}
            </button>
          )}
        </div>
      </div>

      {showChart && insight.data?.labels && (
        <div className="mt-3">
          <ResultChart
            columns={['label', 'value']}
            rows={insight.data.labels.map((l, i) => [l, insight.data.values[i]])}
          />
        </div>
      )}
    </div>
  )
}

export default function InsightsPage() {
  const [selectedConn, setSelectedConn] = useState('')
  const [report, setReport] = useState(null)

  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const analyzeMutation = useMutation({
    mutationFn: (connId) => api.post(`/insights/${connId}`).then(r => r.data),
    onSuccess: setReport,
  })

  const groupedInsights = report?.insights?.reduce((acc, i) => {
    if (!acc[i.type]) acc[i.type] = []
    acc[i.type].push(i)
    return acc
  }, {}) || {}

  const criticalCount = report?.insights?.filter(i => i.severity === 'critical').length || 0
  const warningCount = report?.insights?.filter(i => i.severity === 'warning').length || 0

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Auto Insights</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Automatic data analysis — no questions needed
          </p>
        </div>

        {/* Connection selector + Analyze button */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-6">
          <div className="flex gap-3 items-end">
            <div className="flex-1">
              <label className="block text-xs text-gray-400 mb-1.5">Select Database</label>
              <select value={selectedConn} onChange={e => { setSelectedConn(e.target.value); setReport(null) }}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm focus:outline-none focus:border-blue-500">
                <option value="">Choose a database...</option>
                {connections.map(c => (
                  <option key={c.id} value={c.id}>
                    {c.db_type === 'sqlite' ? '📁' : c.db_type === 'mysql' ? '🐬' : '🐘'} {c.name}
                  </option>
                ))}
              </select>
            </div>
            <button
              onClick={() => analyzeMutation.mutate(selectedConn)}
              disabled={!selectedConn || analyzeMutation.isPending}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
              {analyzeMutation.isPending ? (
                <span className="flex items-center gap-2">
                  <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Analyzing...
                </span>
              ) : '✨ Analyze Database'}
            </button>
          </div>

          {!connections.length && (
            <p className="text-xs text-gray-600 mt-3">
              No databases connected. <Link to="/connections" className="text-blue-400">Add one →</Link>
            </p>
          )}
        </div>

        {/* Report */}
        {analyzeMutation.isPending && (
          <div className="text-center py-16">
            <div className="w-10 h-10 border-2 border-gray-700 border-t-blue-500 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-400 font-medium">Analyzing your database...</p>
            <p className="text-gray-600 text-sm mt-1">Running diagnostic queries in parallel</p>
          </div>
        )}

        {analyzeMutation.isError && (
          <div className="bg-red-950 border border-red-800 rounded-xl p-4">
            <p className="text-red-400 text-sm">{analyzeMutation.error?.response?.data?.detail || 'Analysis failed'}</p>
          </div>
        )}

        {report && !analyzeMutation.isPending && (
          <div className="space-y-6">
            {/* Header stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                { label: 'Tables', value: report.total_tables },
                { label: 'Total Rows', value: report.total_rows?.toLocaleString() },
                { label: 'Insights', value: report.insights?.length },
                { label: 'Generated in', value: `${(report.generated_in_ms / 1000).toFixed(1)}s` },
              ].map(({ label, value }) => (
                <div key={label} className="bg-gray-900 border border-gray-800 rounded-xl p-3 text-center">
                  <p className="text-gray-500 text-xs">{label}</p>
                  <p className="text-white font-bold text-lg mt-0.5">{value}</p>
                </div>
              ))}
            </div>

            {/* Warnings banner */}
            {(criticalCount > 0 || warningCount > 0) && (
              <div className="bg-yellow-950/40 border border-yellow-800 rounded-xl px-4 py-3 flex items-center gap-3">
                <span className="text-xl">⚠️</span>
                <p className="text-yellow-300 text-sm">
                  {criticalCount > 0 && <span>{criticalCount} critical issue{criticalCount > 1 ? 's' : ''} · </span>}
                  {warningCount > 0 && <span>{warningCount} warning{warningCount > 1 ? 's' : ''}</span>} found in your data
                </p>
              </div>
            )}

            {/* AI Summary */}
            {report.summary && (
              <div className="bg-blue-950/30 border border-blue-800 rounded-xl p-4">
                <p className="text-xs text-blue-400 uppercase tracking-wider font-medium mb-2">AI Summary</p>
                <p className="text-white text-sm leading-relaxed">{report.summary}</p>
              </div>
            )}

            {/* Insight cards by type */}
            {Object.entries({
              trend: '📈 Trends',
              anomaly: '⚠️ Anomalies',
              quality: '🔍 Data Quality',
              top_values: '🏆 Top Values',
              summary: '📊 Statistics',
            }).map(([type, label]) => {
              const items = groupedInsights[type]
              if (!items?.length) return null
              return (
                <div key={type}>
                  <h3 className="text-white font-semibold text-sm mb-3">{label}</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    {items.map((insight, i) => (
                      <InsightCard key={i} insight={insight} />
                    ))}
                  </div>
                </div>
              )
            })}

            {/* Ask follow-up */}
            <div className="bg-gray-900 border border-gray-700 rounded-xl p-4 flex items-center justify-between">
              <div>
                <p className="text-white text-sm font-medium">Want to dig deeper?</p>
                <p className="text-gray-500 text-xs mt-0.5">Ask specific questions about your data</p>
              </div>
              <Link to={`/query/${selectedConn}`}
                className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                Query this DB →
              </Link>
            </div>
          </div>
        )}
      </div>
    </AppShell>
  )
}
