import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import AppShell from '../components/ui/AppShell'
import api from '../utils/api'

const SEVERITY_STYLE = {
  error: 'bg-red-950 border-red-800 text-red-400',
  warning: 'bg-yellow-950 border-yellow-800 text-yellow-400',
  info: 'bg-blue-950 border-blue-800 text-blue-400',
}

const SEVERITY_ICON = { error: '✗', warning: '⚠', info: 'ℹ' }

export default function OptimizerPage() {
  const [sql, setSql] = useState('')
  const [dialect, setDialect] = useState('postgres')
  const [result, setResult] = useState(null)
  const [copied, setCopied] = useState(false)

  const optimizeMutation = useMutation({
    mutationFn: (data) => api.post('/query/optimize', data).then(r => r.data),
    onSuccess: setResult,
  })

  const handleOptimize = () => {
    if (!sql.trim()) return
    optimizeMutation.mutate({ sql, dialect })
  }

  const scoreColor = result?.improvement_score > 50 ? 'text-red-400'
    : result?.improvement_score > 20 ? 'text-yellow-400' : 'text-green-400'

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Query Optimizer</h1>
          <p className="text-gray-500 text-sm mt-0.5">
            Paste a SQL query to detect anti-patterns and get an optimized version
          </p>
        </div>

        {/* Input */}
        <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden mb-4">
          <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700">
            <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Input SQL</span>
            <select value={dialect} onChange={e => setDialect(e.target.value)}
              className="bg-gray-800 border border-gray-700 rounded px-2 py-1 text-xs text-gray-400 focus:outline-none">
              <option value="postgres">PostgreSQL</option>
              <option value="mysql">MySQL</option>
              <option value="sqlite">SQLite</option>
            </select>
          </div>
          <textarea
            value={sql}
            onChange={e => setSql(e.target.value)}
            placeholder="Paste your SQL query here..."
            className="w-full bg-transparent text-green-300 font-mono text-sm p-4 resize-none focus:outline-none min-h-[180px] placeholder-gray-700"
          />
        </div>

        <button onClick={handleOptimize}
          disabled={!sql.trim() || optimizeMutation.isPending}
          className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors mb-6">
          {optimizeMutation.isPending ? 'Analyzing...' : 'Analyze & Optimize'}
        </button>

        {result && (
          <div className="space-y-4">
            {/* Score */}
            <div className="flex items-center gap-4 bg-gray-900 border border-gray-700 rounded-xl p-4">
              <div className="text-center">
                <p className={`text-3xl font-bold ${scoreColor}`}>{result.improvement_score}</p>
                <p className="text-xs text-gray-600 mt-0.5">issue score</p>
              </div>
              <div className="flex-1">
                <p className="text-white text-sm font-medium">
                  {result.issues.length === 0 ? 'No issues found — query looks good!' : `${result.issues.length} issue${result.issues.length !== 1 ? 's' : ''} detected`}
                </p>
                {result.explanation && (
                  <p className="text-gray-500 text-xs mt-1">{result.explanation}</p>
                )}
              </div>
            </div>

            {/* Issues */}
            {result.issues.length > 0 && (
              <div className="space-y-2">
                <p className="text-xs text-gray-500 uppercase tracking-wider font-medium">Issues</p>
                {result.issues.map((issue, i) => (
                  <div key={i} className={`border rounded-xl p-3 ${SEVERITY_STYLE[issue.severity] || SEVERITY_STYLE.info}`}>
                    <div className="flex items-start gap-2">
                      <span className="text-sm mt-0.5">{SEVERITY_ICON[issue.severity]}</span>
                      <div>
                        <p className="text-sm font-medium">{issue.message}</p>
                        <p className="text-xs opacity-70 mt-0.5">💡 {issue.suggestion}</p>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* Optimized SQL */}
            {result.has_improvements && result.optimized_sql !== result.original_sql && (
              <div>
                <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-2">Optimized SQL</p>
                <div className="bg-gray-900 border border-green-800 rounded-xl overflow-hidden">
                  <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700">
                    <span className="text-xs text-green-400">Optimized version</span>
                    <button
                      onClick={() => { navigator.clipboard.writeText(result.optimized_sql); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
                      className="text-xs text-gray-400 hover:text-white transition-colors">
                      {copied ? '✓ Copied' : 'Copy'}
                    </button>
                  </div>
                  <pre className="p-4 text-sm text-green-300 font-mono overflow-x-auto whitespace-pre-wrap">
                    {result.optimized_sql}
                  </pre>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
