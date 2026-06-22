import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import AppShell from '../components/ui/AppShell'
import ResultsTable from '../components/editor/ResultsTable'
import ResultChart from '../components/charts/ResultChart'
import api from '../utils/api'

function detectMode(text) {
  const lower = text.toLowerCase()
  const sqlKeywords = ['sql', 'query', 'write a query', 'give me query', 'show query', 'generate sql']
  if (sqlKeywords.some(k => lower.includes(k))) return 'sql'
  return 'qa'
}

function buildChatFromHistory(history, connId) {
  const filtered = connId ? history.filter(q => q.connection_id === connId) : history
  const chat = []
  ;[...filtered].reverse().forEach(q => {
    chat.push({ role: 'user', text: q.natural_language, id: q.id + '_u', fromHistory: true })
    chat.push({
      role: 'assistant', id: q.id + '_a', fromHistory: true,
      data: {
        answer: null,
        generated_sql: q.generated_sql,
        explanation: null,
        guardrail_triggered: q.guardrail_triggered,
        guardrail_reason: q.guardrail_reason,
        execution_result: null,
        tokens_used: q.tokens_used,
        status: q.status,
        fromHistory: true,
      }
    })
  })
  return chat
}

const SUGGESTIONS = [
  "How many records are in this database?",
  "Show me all tables and row counts",
  "What are the top 5 entries?",
  "Give me a summary of the data",
]

export default function QueryPage() {
  const { connectionId } = useParams()
  const qc = useQueryClient()
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  const [nlQuery, setNlQuery] = useState('')
  const [status, setStatus] = useState('idle')
  const [selectedConn, setSelectedConn] = useState(connectionId || '')
  const [viewMode, setViewMode] = useState({})
  const [showSQL, setShowSQL] = useState({})
  const [copied, setCopied] = useState(null)
  const [chat, setChat] = useState([])
  const [showClearConfirm, setShowClearConfirm] = useState(false)
  const [historyInitialized, setHistoryInitialized] = useState(false)

  const { data: connections = [] } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const { data: history = [], isLoading: historyLoading } = useQuery({
    queryKey: ['chat-history', selectedConn],
    queryFn: () => selectedConn
      ? api.get(`/history/?limit=30&connection_id=${selectedConn}`).then(r => r.data)
      : [],
    enabled: !!selectedConn,
  })

  // Load history into chat — only once per connection change
  useEffect(() => {
    if (!selectedConn || historyLoading) return
    setChat(buildChatFromHistory(history, selectedConn))
    setHistoryInitialized(true)
  }, [selectedConn, historyLoading]) // intentionally not including `history` to avoid re-runs

  // Auto scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [chat.length, status])

  const handleInput = (e) => {
    setNlQuery(e.target.value)
    e.target.style.height = 'auto'
    e.target.style.height = Math.min(e.target.scrollHeight, 120) + 'px'
  }

  const generateMutation = useMutation({
    mutationFn: (data) => api.post('/query/generate', data).then(r => r.data),
    onMutate: ({ natural_language }) => {
      setStatus('running')
      setChat(prev => [...prev, {
        role: 'user', text: natural_language, id: Date.now() + '_u'
      }])
    },
    onSuccess: (data) => {
      setStatus(data.guardrail_triggered ? 'blocked' : data.status === 'success' ? 'success' : 'error')
      setChat(prev => [...prev, {
        role: 'assistant', id: Date.now() + '_a', data,
      }])
      qc.invalidateQueries(['chat-history', selectedConn])
    },
    onError: (err) => {
      setStatus('error')
      setChat(prev => [...prev, {
        role: 'assistant', id: Date.now() + '_err',
        data: { error: err.response?.data?.detail || 'Something went wrong. Please try again.' }
      }])
    },
  })

  const clearMutation = useMutation({
    mutationFn: () => api.delete(`/history/clear?connection_id=${selectedConn}`),
    onSuccess: () => {
      setChat([])
      setShowClearConfirm(false)
      setHistoryInitialized(false)
      qc.invalidateQueries(['chat-history', selectedConn])
    },
  })

  const handleSubmit = () => {
    if (!nlQuery.trim() || status === 'running' || !selectedConn) return
    const q = nlQuery.trim()
    setNlQuery('')
    if (textareaRef.current) textareaRef.current.style.height = '48px'
    generateMutation.mutate({
      natural_language: q,
      connection_id: selectedConn,
      mode: detectMode(q),
      execute: true,
    })
  }

  const handleConnectionChange = (id) => {
    setSelectedConn(id)
    setChat([])
    setStatus('idle')
    setShowClearConfirm(false)
    setHistoryInitialized(false)
  }

  return (
    <AppShell>
      <div className="flex flex-col h-full max-w-4xl mx-auto">

        {/* Top bar */}
        <div className="px-6 py-3 border-b border-gray-800 flex items-center gap-3 shrink-0">
          <span className="text-xs text-gray-500 shrink-0">Database:</span>
          <select value={selectedConn} onChange={e => handleConnectionChange(e.target.value)}
            className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-1.5 text-white text-sm focus:outline-none focus:border-blue-500 flex-1 max-w-xs">
            <option value="">Select database...</option>
            {connections.map(c => (
              <option key={c.id} value={c.id}>
                {c.db_type === 'sqlite' ? '📁' : c.db_type === 'mysql' ? '🐬' : '🐘'} {c.name}
              </option>
            ))}
          </select>

          {selectedConn && chat.length > 0 && (
            <div className="ml-auto flex items-center gap-2">
              {showClearConfirm ? (
                <>
                  <span className="text-xs text-red-400">Delete all history for this DB?</span>
                  <button onClick={() => clearMutation.mutate()}
                    disabled={clearMutation.isPending}
                    className="text-xs bg-red-600 hover:bg-red-500 text-white px-2 py-1 rounded transition-colors">
                    {clearMutation.isPending ? 'Clearing...' : 'Yes, delete'}
                  </button>
                  <button onClick={() => setShowClearConfirm(false)}
                    className="text-xs text-gray-500 hover:text-white px-2 py-1 transition-colors">
                    Cancel
                  </button>
                </>
              ) : (
                <button onClick={() => setShowClearConfirm(true)}
                  className="text-xs text-gray-600 hover:text-red-400 transition-colors">
                  Clear history
                </button>
              )}
            </div>
          )}

          {!selectedConn && (
            <Link to="/connections" className="text-xs text-blue-400 hover:text-blue-300 ml-auto">
              + Add database
            </Link>
          )}
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">

          {chat.length === 0 && !historyLoading && (
            <div className="text-center py-16">
              <p className="text-4xl mb-3">💬</p>
              <p className="text-gray-300 font-medium text-lg">
                {selectedConn ? 'Ask anything about your data' : 'Select a database to start'}
              </p>
              <p className="text-gray-600 text-sm mt-1">
                {selectedConn
                  ? 'Ask in plain English — SQL generated automatically'
                  : 'Choose a database from the dropdown above'}
              </p>
              {selectedConn && (
                <div className="mt-6 grid grid-cols-2 gap-2 max-w-md mx-auto">
                  {SUGGESTIONS.map(q => (
                    <button key={q} onClick={() => setNlQuery(q)}
                      className="text-left text-xs text-gray-500 hover:text-white bg-gray-900 hover:bg-gray-800 border border-gray-800 hover:border-gray-600 rounded-xl px-3 py-2.5 transition-colors">
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {historyLoading && selectedConn && (
            <div className="text-center py-8">
              <div className="w-5 h-5 border-2 border-gray-700 border-t-blue-500 rounded-full animate-spin mx-auto" />
              <p className="text-gray-600 text-xs mt-2">Loading history...</p>
            </div>
          )}

          {chat.map((msg, i) => (
            <div key={msg.id || i}>
              {msg.role === 'user' ? (
                <div className="flex justify-end">
                  <div className={`rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-lg text-sm
                    ${msg.fromHistory ? 'bg-blue-900/50 text-blue-200' : 'bg-blue-600 text-white'}`}>
                    {msg.text}
                  </div>
                </div>
              ) : (
                <div className="flex justify-start">
                  <div className="max-w-2xl w-full space-y-2">

                    {msg.data?.guardrail_triggered && (
                      <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-gray-300 text-sm">{msg.data.guardrail_reason}</p>
                      </div>
                    )}

                    {msg.data?.error && (
                      <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-red-400 text-sm">{msg.data.error}</p>
                      </div>
                    )}

                    {msg.data?.answer && (
                      <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-white text-sm leading-relaxed">{msg.data.answer}</p>
                      </div>
                    )}

                    {!msg.data?.answer && msg.data?.explanation && !msg.data?.guardrail_triggered && !msg.data?.error && (
                      <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-white text-sm leading-relaxed">{msg.data.explanation}</p>
                      </div>
                    )}

                    {msg.data?.fromHistory && msg.data?.generated_sql && !msg.data?.answer && !msg.data?.guardrail_triggered && (
                      <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                        <p className="text-gray-500 text-xs italic">Results not stored · Ask again to re-run</p>
                      </div>
                    )}

                    {msg.data?.execution_result?.success && msg.data?.execution_result?.rows?.length > 0 && (
                      <div className="bg-gray-900 border border-gray-700 rounded-xl overflow-hidden">
                        <div className="flex items-center justify-between px-4 py-2 border-b border-gray-800">
                          <span className="text-xs text-gray-500">
                            {msg.data.execution_result.row_count} rows
                            {msg.data.execution_result.truncated && ' (first 1000)'}
                            {' · '}{msg.data.execution_result.execution_time_ms}ms
                          </span>
                          <div className="flex gap-1">
                            {['table', 'chart'].map(v => (
                              <button key={v}
                                onClick={() => setViewMode(prev => ({ ...prev, [i]: v }))}
                                className={`px-2 py-0.5 text-xs rounded transition-colors
                                  ${(viewMode[i] || 'table') === v ? 'bg-gray-700 text-white' : 'text-gray-600 hover:text-white'}`}>
                                {v === 'table' ? '📋' : '📊'} {v}
                              </button>
                            ))}
                          </div>
                        </div>
                        {(viewMode[i] || 'table') === 'table'
                          ? <ResultsTable columns={msg.data.execution_result.columns} rows={msg.data.execution_result.rows} />
                          : <ResultChart columns={msg.data.execution_result.columns} rows={msg.data.execution_result.rows} />
                        }
                      </div>
                    )}

                    {msg.data?.execution_result?.error && (
                      <div className="bg-red-950/40 border border-red-900 rounded-xl px-4 py-3">
                        <p className="text-red-400 text-xs font-mono">{msg.data.execution_result.error}</p>
                      </div>
                    )}

                    {msg.data?.generated_sql && (
                      <div>
                        <button onClick={() => setShowSQL(prev => ({ ...prev, [i]: !prev[i] }))}
                          className="text-xs text-gray-600 hover:text-gray-400 transition-colors flex items-center gap-1.5 mt-1">
                          {showSQL[i] ? '▼' : '▶'} View SQL
                          {msg.data.tokens_used > 0 && <span className="text-gray-700">· {msg.data.tokens_used} tokens</span>}
                        </button>
                        {showSQL[i] && (
                          <div className="mt-2 bg-gray-950 border border-gray-800 rounded-xl overflow-hidden">
                            <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-800">
                              <span className="text-xs text-gray-600">SQL</span>
                              <button onClick={() => { navigator.clipboard.writeText(msg.data.generated_sql); setCopied(i); setTimeout(() => setCopied(null), 2000) }}
                                className="text-xs text-gray-600 hover:text-white transition-colors">
                                {copied === i ? '✓ Copied' : 'Copy'}
                              </button>
                            </div>
                            <pre className="p-3 text-xs text-green-300 font-mono overflow-x-auto whitespace-pre-wrap">
                              {msg.data.generated_sql}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}

          {status === 'running' && (
            <div className="flex justify-start">
              <div className="bg-gray-900 border border-gray-700 rounded-2xl rounded-tl-sm px-4 py-3">
                <div className="flex gap-1">
                  {[0,1,2].map(i => (
                    <span key={i} className="w-1.5 h-1.5 rounded-full bg-gray-500 animate-bounce"
                      style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="px-6 py-4 border-t border-gray-800 shrink-0">
          {!selectedConn && (
            <p className="text-xs text-orange-400/80 mb-2 text-center">Select a database above to start</p>
          )}
          <div className="flex gap-3 items-end">
            <textarea ref={textareaRef} value={nlQuery} onChange={handleInput}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSubmit() } }}
              placeholder={selectedConn ? "Ask anything... (Enter to send)" : "Select a database first..."}
              disabled={status === 'running' || !selectedConn}
              rows={1}
              className="flex-1 bg-gray-900 border border-gray-700 rounded-xl text-gray-100 placeholder-gray-600 px-4 py-3 resize-none focus:outline-none focus:border-blue-500 transition-colors text-sm disabled:opacity-50"
              style={{ minHeight: '48px', maxHeight: '120px' }}
            />
            <button onClick={handleSubmit}
              disabled={!nlQuery.trim() || status === 'running' || !selectedConn}
              className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white p-3 rounded-xl transition-colors shrink-0 h-12 w-12 flex items-center justify-center">
              {status === 'running' ? (
                <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </AppShell>
  )
}