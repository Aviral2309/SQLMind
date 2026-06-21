import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import AppShell from '../components/ui/AppShell'
import api from '../utils/api'

const STATUS_BADGE = {
  success: 'bg-green-950 text-green-400 border-green-800',
  failed: 'bg-red-950 text-red-400 border-red-800',
  guardrail_blocked: 'bg-orange-950 text-orange-400 border-orange-800',
  running: 'bg-blue-950 text-blue-400 border-blue-800',
}

export default function HistoryPage() {
  const [expanded, setExpanded] = useState(null)

  const { data: history = [], isLoading } = useQuery({
    queryKey: ['history-full'],
    queryFn: () => api.get('/query/history?limit=50').then(r => r.data),
  })

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Query History</h1>
          <p className="text-gray-500 text-sm mt-0.5">{history.length} queries</p>
        </div>

        {isLoading ? (
          <div className="text-gray-500 text-sm">Loading...</div>
        ) : history.length === 0 ? (
          <div className="bg-gray-900 border border-gray-800 rounded-xl p-10 text-center">
            <p className="text-gray-500">No queries yet.</p>
          </div>
        ) : (
          <div className="space-y-2">
            {history.map(q => (
              <div key={q.id} className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden">
                {/* Row */}
                <button
                  onClick={() => setExpanded(expanded === q.id ? null : q.id)}
                  className="w-full flex items-center gap-4 px-4 py-3 hover:bg-gray-800/50 transition-colors text-left"
                >
                  <span className={`shrink-0 text-xs px-2 py-0.5 rounded border ${STATUS_BADGE[q.status] || STATUS_BADGE.failed}`}>
                    {q.status}
                  </span>
                  <p className="flex-1 text-white text-sm truncate">{q.natural_language}</p>
                  <div className="shrink-0 flex items-center gap-3 text-xs text-gray-600">
                    {q.execution_time_ms && <span>{Math.round(q.execution_time_ms)}ms</span>}
                    <span>{new Date(q.created_at).toLocaleString()}</span>
                    <span>{expanded === q.id ? '▲' : '▼'}</span>
                  </div>
                </button>

                {/* Expanded */}
                {expanded === q.id && (
                  <div className="border-t border-gray-800 px-4 py-4 space-y-3">
                    {q.generated_sql && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">Generated SQL</p>
                        <pre className="bg-gray-950 rounded-lg p-3 text-green-300 text-xs font-mono overflow-x-auto whitespace-pre-wrap">
                          {q.generated_sql}
                        </pre>
                      </div>
                    )}

                    {q.eval_scores && (
                      <div>
                        <p className="text-xs text-gray-500 uppercase tracking-wider mb-1.5">Eval Scores</p>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                          {Object.entries(q.eval_scores).map(([k, v]) => (
                            <div key={k} className="bg-gray-950 rounded-lg p-2.5">
                              <p className="text-xs text-gray-600">{k.replace(/_/g, ' ')}</p>
                              <p className="text-white font-mono text-sm mt-0.5">
                                {typeof v === 'number' ? v.toFixed(3) : v}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {q.guardrail_triggered && (
                      <div className="bg-orange-950 border border-orange-800 rounded-lg p-3">
                        <p className="text-orange-400 text-xs">🛡️ Guardrail triggered — query was blocked</p>
                      </div>
                    )}

                    <div className="flex gap-4 text-xs text-gray-600">
                      {q.tokens_used && <span>Tokens: {q.tokens_used}</span>}
                      <span>ID: {q.id.slice(0, 8)}...</span>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  )
}
