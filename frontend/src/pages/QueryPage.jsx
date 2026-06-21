import { useState, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import AppShell from '../components/ui/AppShell'
import AgentStepViewer from '../components/editor/AgentStepViewer'
import ResultsTable from '../components/editor/ResultsTable'
import ResultChart from '../components/charts/ResultChart'
import api from '../utils/api'

export default function QueryPage() {
  const { connectionId } = useParams()
  const [nlQuery, setNlQuery] = useState('')
  const [mode, setMode] = useState('qa') // qa is default now
  const [status, setStatus] = useState('idle')
  const [agentSteps, setAgentSteps] = useState([])
  const [result, setResult] = useState(null)
  const [selectedConn, setSelectedConn] = useState(connectionId || '')
  const [viewMode, setViewMode] = useState('table')
  const [copied, setCopied] = useState(false)
  const [sqlFile, setSqlFile] = useState(null)
  const [sqlFileResult, setSqlFileResult] = useState(null)
  const [activeTab, setActiveTab] = useState('nl') // nl | sql_file
  const fileRef = useRef()

  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const generateMutation = useMutation({
    mutationFn: (data) => api.post('/query/generate', data).then(r => r.data),
    onMutate: () => { setStatus('running'); setResult(null); setAgentSteps([]) },
    onSuccess: (data) => {
      setStatus(data.guardrail_triggered ? 'blocked' : data.status === 'success' ? 'success' : 'error')
      setResult(data)
      if (data.agent_steps) setAgentSteps(data.agent_steps)
    },
    onError: () => setStatus('error'),
  })

  const sqlFileMutation = useMutation({
    mutationFn: async ({ file, connectionId }) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('connection_id', connectionId)
      return api.post('/query/upload-sql', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
    },
    onSuccess: (data) => setSqlFileResult(data),
    onError: (err) => setSqlFileResult({ error: err.response?.data?.detail || 'Failed' }),
  })

  const handleSubmit = () => {
    if (!nlQuery.trim() || status === 'running' || !selectedConn) return
    generateMutation.mutate({ natural_language: nlQuery, connection_id: selectedConn, mode, execute: true })
  }

  const handleSqlFileUpload = () => {
    if (!sqlFile || !selectedConn) return
    sqlFileMutation.mutate({ file: sqlFile, connectionId: selectedConn })
  }

  const statusDot = { idle:'bg-gray-600', running:'bg-blue-500 animate-pulse', success:'bg-green-500', error:'bg-red-500', blocked:'bg-orange-500' }[status] || 'bg-gray-600'
  const hasResults = result?.execution_result?.success && result?.execution_result?.rows?.length > 0

  return (
    <AppShell>
      <div className="flex flex-col p-6 gap-4 max-w-5xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold text-white">Query Editor</h1>
          <div className="flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${statusDot}`} />
            <span className="text-xs text-gray-500">{status}</span>
          </div>
        </div>

        {/* DB selector */}
        <div className="flex flex-wrap items-end gap-4">
          <div className="flex-1 min-w-48">
            <label className="block text-xs text-gray-500 mb-1.5">Database</label>
            <select value={selectedConn} onChange={e => setSelectedConn(e.target.value)}
              className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500">
              <option value="">Select database...</option>
              {connections.map(c => <option key={c.id} value={c.id}>{c.db_type === 'sqlite' ? '📁' : '🐘'} {c.name}</option>)}
            </select>
          </div>
          {!selectedConn && <Link to="/connections" className="text-xs text-blue-400 hover:text-blue-300 pb-2">+ Add database</Link>}
        </div>

        {/* Input tabs */}
        <div className="flex rounded-lg overflow-hidden border border-gray-700 w-fit">
          {[['nl', '💬 Ask in English'], ['sql_file', '📄 Upload SQL File']].map(([key, label]) => (
            <button key={key} onClick={() => setActiveTab(key)}
              className={`px-4 py-2 text-sm font-medium transition-colors ${activeTab === key ? 'bg-blue-600 text-white' : 'bg-gray-900 text-gray-400 hover:text-white'}`}>
              {label}
            </button>
          ))}
        </div>

        {activeTab === 'nl' ? (
          <>
            {/* Mode toggle */}
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">Output:</span>
              <div className="flex rounded-lg overflow-hidden border border-gray-700">
                {[['qa', '💬 Answer + SQL'], ['sql', '⚡ SQL only']].map(([m, label]) => (
                  <button key={m} onClick={() => setMode(m)}
                    className={`px-3 py-1.5 text-xs font-medium transition-colors ${mode === m ? 'bg-blue-600 text-white' : 'bg-gray-900 text-gray-400 hover:text-white'}`}>
                    {label}
                  </button>
                ))}
              </div>
              {mode === 'qa' && <span className="text-xs text-blue-400/70">Runs query + gives direct answer</span>}
            </div>

            {/* NL input */}
            <div className="relative">
              <textarea value={nlQuery} onChange={e => setNlQuery(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmit() }}
                placeholder={mode === 'qa'
                  ? 'Ask anything... e.g. "How many users signed up this week?"'
                  : 'Describe query... e.g. "Top 10 users by query count"'
                }
                disabled={status === 'running'}
                className="w-full bg-gray-900 border border-gray-700 rounded-xl text-gray-100 placeholder-gray-600 p-4 pr-32 resize-none focus:outline-none focus:border-blue-500 transition-colors min-h-[100px] font-mono text-sm disabled:opacity-60" />
              <button onClick={handleSubmit} disabled={!nlQuery.trim() || status === 'running' || !selectedConn}
                className="absolute bottom-4 right-4 bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
                {status === 'running' ? (
                  <span className="flex items-center gap-1.5">
                    <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Running
                  </span>
                ) : mode === 'qa' ? 'Ask ⌘↵' : 'Generate ⌘↵'}
              </button>
            </div>
          </>
        ) : (
          /* SQL File upload tab */
          <div className="space-y-3">
            <div className="border-2 border-dashed border-gray-700 rounded-xl p-8 text-center hover:border-gray-500 transition-colors">
              <input type="file" accept=".sql" onChange={e => setSqlFile(e.target.files[0])}
                className="hidden" id="sql-upload" ref={fileRef} />
              <label htmlFor="sql-upload" className="cursor-pointer">
                <p className="text-gray-400 text-sm">
                  {sqlFile ? <span className="text-green-400">✓ {sqlFile.name}</span> : <>Drop .sql file or <span className="text-blue-400">browse</span></>}
                </p>
                <p className="text-gray-600 text-xs mt-1">Executes SQL file on selected database (max 5MB)</p>
              </label>
            </div>
            <button onClick={handleSqlFileUpload}
              disabled={!sqlFile || !selectedConn || sqlFileMutation.isPending}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors">
              {sqlFileMutation.isPending ? 'Executing...' : 'Execute SQL File'}
            </button>
            {sqlFileResult && (
              <div className={`rounded-xl border p-4 ${sqlFileResult.error ? 'bg-red-950 border-red-800' : 'bg-green-950 border-green-800'}`}>
                <p className={`text-sm font-medium ${sqlFileResult.error ? 'text-red-400' : 'text-green-400'}`}>
                  {sqlFileResult.error || sqlFileResult.message}
                </p>
                {sqlFileResult.row_count > 0 && (
                  <p className="text-xs text-gray-500 mt-1">{sqlFileResult.row_count} rows · {sqlFileResult.execution_time_ms}ms</p>
                )}
              </div>
            )}
            {sqlFileResult?.rows?.length > 0 && (
              <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                <ResultsTable columns={sqlFileResult.columns} rows={sqlFileResult.rows} />
              </div>
            )}
          </div>
        )}

        {/* Guardrail block */}
        {result?.guardrail_triggered && (
          <div className="bg-orange-950 border border-orange-800 rounded-xl p-4">
            <p className="text-orange-300 font-medium text-sm">🛡️ Blocked by guardrails</p>
            <p className="text-orange-500 text-xs mt-1 font-mono">{result.guardrail_reason}</p>
          </div>
        )}

        {/* Agent trace */}
        {agentSteps.length > 0 && <AgentStepViewer steps={agentSteps} status={status} />}

        {/* Q&A Answer — shown prominently at top */}
        {result?.answer && (
          <div className="bg-gradient-to-r from-blue-950 to-indigo-950 border border-blue-700 rounded-xl p-5">
            <p className="text-xs text-blue-400 uppercase tracking-wider font-medium mb-2">Answer</p>
            <p className="text-white text-lg leading-relaxed font-medium">{result.answer}</p>
          </div>
        )}

        {/* Generated SQL */}
        {result?.generated_sql && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700">
              <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Generated SQL</span>
              <div className="flex items-center gap-3">
                {result.tokens_used > 0 && <span className="text-xs text-gray-600">{result.tokens_used} tokens</span>}
                {result.execution_time_ms > 0 && <span className="text-xs text-gray-600">{Math.round(result.execution_time_ms)}ms total</span>}
                <button onClick={() => { navigator.clipboard.writeText(result.generated_sql); setCopied(true); setTimeout(() => setCopied(false), 2000) }}
                  className="text-xs text-gray-400 hover:text-white transition-colors">{copied ? '✓ Copied' : 'Copy'}</button>
              </div>
            </div>
            <pre className="p-4 text-sm text-green-300 font-mono overflow-x-auto whitespace-pre-wrap leading-relaxed">{result.generated_sql}</pre>
          </div>
        )}

        {/* Explanation */}
        {result?.explanation && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-4">
            <p className="text-xs text-gray-500 uppercase tracking-wider font-medium mb-2">How this query works</p>
            <p className="text-gray-300 text-sm leading-relaxed">{result.explanation}</p>
          </div>
        )}

        {/* Results */}
        {result?.execution_result && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
            <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-700">
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Results</span>
                {result.execution_result.success && (
                  <span className="text-xs text-gray-600">
                    {result.execution_result.row_count} rows
                    {result.execution_result.truncated && ' (showing first 1000)'}
                    {' · '}{result.execution_result.execution_time_ms}ms
                  </span>
                )}
              </div>
              {hasResults && (
                <div className="flex rounded-lg overflow-hidden border border-gray-700">
                  {['table', 'chart'].map(v => (
                    <button key={v} onClick={() => setViewMode(v)}
                      className={`px-2.5 py-1 text-xs capitalize transition-colors ${viewMode === v ? 'bg-gray-700 text-white' : 'text-gray-500 hover:text-white'}`}>
                      {v === 'table' ? '📋 Table' : '📊 Chart'}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {result.execution_result.error ? (
              <div className="p-4"><p className="text-red-400 text-sm font-mono">{result.execution_result.error}</p></div>
            ) : hasResults ? (
              viewMode === 'table'
                ? <ResultsTable columns={result.execution_result.columns} rows={result.execution_result.rows} />
                : <ResultChart columns={result.execution_result.columns} rows={result.execution_result.rows} />
            ) : (
              <div className="p-6 text-center text-gray-600 text-sm">No rows returned</div>
            )}
          </div>
        )}
      </div>
    </AppShell>
  )
}
