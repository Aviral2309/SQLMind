import { useState, useRef } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import AppShell from '../components/ui/AppShell'
import api from '../utils/api'

const FILE_TYPES = [
  { ext: 'csv',    icon: '📊', label: 'CSV',    desc: 'Auto-detects delimiter' },
  { ext: 'xlsx',   icon: '📗', label: 'Excel',  desc: 'Each sheet = table' },
  { ext: 'db',     icon: '🗄️', label: 'SQLite', desc: 'SQLite database' },
  { ext: 'sql',    icon: '📄', label: 'SQL',    desc: 'Runs & creates DB' },
  { ext: 'json',   icon: '📋', label: 'JSON',   desc: 'Array of objects' },
  { ext: 'tsv',    icon: '📑', label: 'TSV',    desc: 'Tab separated' },
]

const ACCEPT_ALL = '.csv,.tsv,.db,.sqlite,.sqlite3,.xlsx,.xls,.json,.sql'

const DB_CONFIGS = {
  postgres: {
    label: 'PostgreSQL',
    icon: '🐘',
    color: 'border-blue-700 bg-blue-950/30',
    defaultPort: '5432',
    placeholder: { host: 'localhost', database: 'mydb', username: 'postgres' },
    buildUrl: (f) => `postgresql://${encodeURIComponent(f.username)}:${encodeURIComponent(f.password)}@${f.host}:${f.port}/${f.database}`,
  },
  mysql: {
    label: 'MySQL',
    icon: '🐬',
    color: 'border-orange-700 bg-orange-950/30',
    defaultPort: '3306',
    placeholder: { host: 'localhost', database: 'mydb', username: 'root' },
    buildUrl: (f) => `mysql+pymysql://${encodeURIComponent(f.username)}:${encodeURIComponent(f.password)}@${f.host}:${f.port}/${f.database}`,
  },
  mariadb: {
    label: 'MariaDB',
    icon: '🦭',
    color: 'border-orange-700 bg-orange-950/30',
    defaultPort: '3306',
    placeholder: { host: 'localhost', database: 'mydb', username: 'root' },
    buildUrl: (f) => `mysql+pymysql://${encodeURIComponent(f.username)}:${encodeURIComponent(f.password)}@${f.host}:${f.port}/${f.database}`,
  },
  mssql: {
    label: 'SQL Server',
    icon: '🪟',
    color: 'border-red-700 bg-red-950/30',
    defaultPort: '1433',
    placeholder: { host: 'localhost', database: 'mydb', username: 'sa' },
    buildUrl: (f) => `mssql+pyodbc://${encodeURIComponent(f.username)}:${encodeURIComponent(f.password)}@${f.host}:${f.port}/${f.database}?driver=ODBC+Driver+17+for+SQL+Server`,
  },
  sqlite: {
    label: 'SQLite File Path',
    icon: '📁',
    color: 'border-green-700 bg-green-950/30',
    defaultPort: '',
    placeholder: { host: '', database: '/path/to/file.db', username: '' },
    buildUrl: (f) => `sqlite:///${f.database}`,
  },
  url: {
    label: 'Raw URL',
    icon: '🔗',
    color: 'border-gray-700 bg-gray-900',
    defaultPort: '',
    placeholder: { host: '', database: '', username: '' },
    buildUrl: (f) => f.rawUrl || '',
  },
}

export default function ConnectionsPage() {
  const qc = useQueryClient()
  const [tab, setTab] = useState('upload')
  const [dbType, setDbType] = useState('mysql')
  const [connForm, setConnForm] = useState({
    name: '', host: 'localhost', port: '3306',
    username: '', password: '', database: '', rawUrl: '',
    showPassword: false,
  })
  const [uploadFile, setUploadFile] = useState(null)
  const [uploadName, setUploadName] = useState('')
  const [feedback, setFeedback] = useState(null)
  const [preview, setPreview] = useState(null)
  const [dragging, setDragging] = useState(false)
  const fileRef = useRef()

  const { data: connections = [], isLoading } = useQuery({
    queryKey: ['connections'],
    queryFn: () => api.get('/schema/connections').then(r => r.data),
  })

  const addMutation = useMutation({
    mutationFn: (data) => api.post('/schema/connections', data),
    onSuccess: () => {
      qc.invalidateQueries(['connections'])
      setConnForm({ name: '', host: 'localhost', port: DB_CONFIGS[dbType]?.defaultPort || '', username: '', password: '', database: '', rawUrl: '', showPassword: false })
      setFeedback({ ok: true, msg: 'Connection added and tested successfully!' })
    },
    onError: (err) => setFeedback({ ok: false, msg: err.response?.data?.detail || 'Connection failed — check credentials' }),
  })

  const uploadMutation = useMutation({
    mutationFn: async ({ file, name }) => {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('name', name || file.name)
      return api.post('/files/database', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
    },
    onSuccess: (data) => {
      qc.invalidateQueries(['connections'])
      setUploadFile(null); setUploadName(''); setPreview(null)
      setFeedback({ ok: true, msg: data.message, detail: data.file_info })
    },
    onError: (err) => setFeedback({ ok: false, msg: err.response?.data?.detail || 'Upload failed' }),
  })

  const previewMutation = useMutation({
    mutationFn: async (file) => {
      const ext = file.name.split('.').pop().toLowerCase()
      if (ext === 'sql') return null
      const fd = new FormData()
      fd.append('file', file)
      return api.post('/files/preview', fd, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data)
    },
    onSuccess: setPreview,
    onError: () => setPreview(null),
  })

  const deleteMutation = useMutation({
    mutationFn: (id) => api.delete(`/schema/connections/${id}`),
    onSuccess: () => qc.invalidateQueries(['connections']),
  })

  const handleDbTypeChange = (type) => {
    setDbType(type)
    setConnForm(f => ({ ...f, port: DB_CONFIGS[type]?.defaultPort || '' }))
    setFeedback(null)
  }

  const handleConnect = () => {
    const config = DB_CONFIGS[dbType]
    const connection_string = config.buildUrl(connForm)
    const db_type = ['mysql', 'mariadb'].includes(dbType) ? 'mysql'
      : dbType === 'mssql' ? 'mssql'
      : dbType === 'sqlite' ? 'sqlite'
      : dbType === 'url' ? 'postgres'
      : dbType
    addMutation.mutate({
      name: connForm.name || `${config.label} — ${connForm.database || connForm.host}`,
      db_type,
      connection_string,
    })
  }

  const handleFileSelect = (file) => {
    if (!file) return
    setUploadFile(file)
    setUploadName(file.name.replace(/\.[^.]+$/, ''))
    setFeedback(null); setPreview(null)
    previewMutation.mutate(file)
  }

  const getExt = (filename) => filename?.split('.').pop()?.toLowerCase() || ''
  const getFileConfig = (filename) => FILE_TYPES.find(f => f.ext === getExt(filename)) || { icon: '📄', label: '' }
  const formatSize = (b) => b < 1024 ? `${b} B` : b < 1048576 ? `${(b/1024).toFixed(1)} KB` : `${(b/1048576).toFixed(1)} MB`
  const isSqlFile = uploadFile && getExt(uploadFile.name) === 'sql'

  const isConnFormValid = () => {
    if (!connForm.name && !connForm.database) return false
    if (dbType === 'url') return !!connForm.rawUrl
    if (dbType === 'sqlite') return !!connForm.database
    return connForm.host && connForm.username && connForm.database
  }

  return (
    <AppShell>
      <div className="p-6 max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-white">Connections</h1>
          <p className="text-gray-500 text-sm mt-0.5">Connect any database or upload a file</p>
        </div>

        {/* Tabs */}
        <div className="flex rounded-xl overflow-hidden border border-gray-700 mb-6 w-fit">
          {[['upload', '📁', 'Upload File'], ['connect', '🔌', 'Connect Database']].map(([key, icon, label]) => (
            <button key={key} onClick={() => { setTab(key); setFeedback(null); setPreview(null) }}
              className={`flex items-center gap-2 px-5 py-2.5 text-sm font-medium transition-colors
                ${tab === key ? 'bg-blue-600 text-white' : 'bg-gray-900 text-gray-400 hover:text-white'}`}>
              <span>{icon}</span>{label}
            </button>
          ))}
        </div>

        {/* ── Connect Database Tab ── */}
        {tab === 'connect' && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-6 space-y-5">
            <h2 className="text-white font-semibold">Connect a Database</h2>

            {/* DB Type selector */}
            <div>
              <label className="block text-xs text-gray-400 mb-2">Database Type</label>
              <div className="grid grid-cols-3 md:grid-cols-6 gap-2">
                {Object.entries(DB_CONFIGS).map(([key, cfg]) => (
                  <button key={key} onClick={() => handleDbTypeChange(key)}
                    className={`flex flex-col items-center gap-1 p-3 rounded-xl border text-xs font-medium transition-all
                      ${dbType === key ? cfg.color + ' border-opacity-100' : 'border-gray-700 bg-gray-800 text-gray-500 hover:text-white hover:border-gray-500'}`}>
                    <span className="text-xl">{cfg.icon}</span>
                    <span className={dbType === key ? 'text-white' : ''}>{cfg.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Connection Name */}
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Connection Name <span className="text-gray-600">(optional)</span></label>
              <input value={connForm.name} onChange={e => setConnForm(f => ({...f, name: e.target.value}))}
                placeholder={`My ${DB_CONFIGS[dbType]?.label} DB`}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
            </div>

            {/* Raw URL mode */}
            {dbType === 'url' ? (
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Connection URL</label>
                <input value={connForm.rawUrl} onChange={e => setConnForm(f => ({...f, rawUrl: e.target.value}))}
                  placeholder="postgresql://user:pass@host:5432/dbname"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 font-mono" />
              </div>
            ) : dbType === 'sqlite' ? (
              /* SQLite — just file path */
              <div>
                <label className="block text-xs text-gray-400 mb-1.5">Database File Path</label>
                <input value={connForm.database} onChange={e => setConnForm(f => ({...f, database: e.target.value}))}
                  placeholder="/path/to/your/database.db"
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 font-mono" />
                <p className="text-xs text-gray-600 mt-1">Or use Upload File tab to upload a .db file directly</p>
              </div>
            ) : (
              /* Full form for MySQL/PostgreSQL/MSSQL */
              <div className="space-y-4">
                <div className="grid grid-cols-3 gap-3">
                  <div className="col-span-2">
                    <label className="block text-xs text-gray-400 mb-1.5">Host</label>
                    <input value={connForm.host} onChange={e => setConnForm(f => ({...f, host: e.target.value}))}
                      placeholder={DB_CONFIGS[dbType]?.placeholder?.host || 'localhost'}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1.5">Port</label>
                    <input value={connForm.port} onChange={e => setConnForm(f => ({...f, port: e.target.value}))}
                      placeholder={DB_CONFIGS[dbType]?.defaultPort}
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                  </div>
                </div>

                <div>
                  <label className="block text-xs text-gray-400 mb-1.5">Database Name</label>
                  <input value={connForm.database} onChange={e => setConnForm(f => ({...f, database: e.target.value}))}
                    placeholder={DB_CONFIGS[dbType]?.placeholder?.database || 'mydb'}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1.5">Username</label>
                    <input value={connForm.username} onChange={e => setConnForm(f => ({...f, username: e.target.value}))}
                      placeholder={DB_CONFIGS[dbType]?.placeholder?.username || 'username'}
                      autoComplete="off"
                      className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1.5">Password</label>
                    <div className="relative">
                      <input
                        type={connForm.showPassword ? 'text' : 'password'}
                        value={connForm.password}
                        onChange={e => setConnForm(f => ({...f, password: e.target.value}))}
                        placeholder="••••••••"
                        autoComplete="new-password"
                        className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 pr-10 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                      <button
                        type="button"
                        onClick={() => setConnForm(f => ({...f, showPassword: !f.showPassword}))}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs transition-colors">
                        {connForm.showPassword ? '🙈' : '👁️'}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Generated URL preview */}
                <div className="bg-gray-800 rounded-lg px-3 py-2">
                  <p className="text-xs text-gray-500 mb-0.5">Connection string (auto-generated)</p>
                  <p className="text-xs text-gray-400 font-mono break-all">
                    {DB_CONFIGS[dbType]?.buildUrl({
                      ...connForm,
                      password: connForm.password ? '••••••' : '',
                    })}
                  </p>
                </div>
              </div>
            )}

            <button onClick={handleConnect}
              disabled={!isConnFormValid() || addMutation.isPending}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white py-3 rounded-xl text-sm font-medium transition-colors">
              {addMutation.isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Testing connection...
                </span>
              ) : 'Test & Connect'}
            </button>

            {feedback && (
              <div className={`rounded-xl px-4 py-3 border text-sm ${feedback.ok ? 'bg-green-950 border-green-800 text-green-400' : 'bg-red-950 border-red-800 text-red-400'}`}>
                {feedback.ok ? '✓ ' : '✗ '}{feedback.msg}
                {feedback.ok && (
                  <Link to="/query" className="ml-2 text-green-300 underline text-xs hover:text-green-200">
                    Start querying →
                  </Link>
                )}
              </div>
            )}

            {/* Install hints */}
            {dbType === 'mysql' || dbType === 'mariadb' ? (
              <p className="text-xs text-gray-600">
                Requires: <code className="text-gray-500">pip install pymysql</code>
              </p>
            ) : dbType === 'mssql' ? (
              <p className="text-xs text-gray-600">
                Requires: <code className="text-gray-500">pip install pyodbc</code> + ODBC Driver 17
              </p>
            ) : null}
          </div>
        )}

        {/* ── Upload File Tab ── */}
        {tab === 'upload' && (
          <div className="bg-gray-900 border border-gray-700 rounded-xl p-5 mb-6">
            <h2 className="text-white font-semibold mb-1">Upload any file</h2>
            <p className="text-gray-500 text-xs mb-4">Instantly queryable — no setup needed</p>

            {/* File type grid */}
            <div className="grid grid-cols-3 md:grid-cols-6 gap-2 mb-5">
              {FILE_TYPES.map(({ ext, icon, label, desc }) => (
                <div key={ext} onClick={() => fileRef.current?.click()}
                  className="bg-gray-800 hover:bg-gray-700 rounded-xl p-3 text-center cursor-pointer transition-colors border border-transparent hover:border-gray-600">
                  <p className="text-2xl">{icon}</p>
                  <p className="text-white text-xs font-medium mt-1">.{ext}</p>
                  <p className="text-gray-600 text-xs mt-0.5 leading-tight">{desc}</p>
                </div>
              ))}
            </div>

            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setDragging(true) }}
              onDragLeave={() => setDragging(false)}
              onDrop={e => { e.preventDefault(); setDragging(false); handleFileSelect(e.dataTransfer.files[0]) }}
              onClick={() => fileRef.current?.click()}
              className={`border-2 border-dashed rounded-xl p-10 text-center transition-all cursor-pointer
                ${dragging ? 'border-blue-500 bg-blue-950/20'
                  : uploadFile ? 'border-green-700 bg-green-950/10'
                  : 'border-gray-700 hover:border-gray-500 hover:bg-gray-800/30'}`}>
              <input ref={fileRef} type="file" accept={ACCEPT_ALL}
                onChange={e => handleFileSelect(e.target.files[0])} className="hidden" />
              {uploadFile ? (
                <div>
                  <p className="text-4xl mb-2">{getFileConfig(uploadFile.name).icon}</p>
                  <p className="text-green-400 font-semibold">{uploadFile.name}</p>
                  <p className="text-gray-500 text-xs mt-1">{formatSize(uploadFile.size)}</p>
                  {isSqlFile && (
                    <p className="text-blue-400 text-xs mt-2 bg-blue-950/40 rounded-lg px-3 py-1.5 inline-block">
                      SQL statements will run automatically on a fresh database
                    </p>
                  )}
                  {previewMutation.isPending && <p className="text-gray-500 text-xs mt-2">Loading preview...</p>}
                </div>
              ) : (
                <div>
                  <p className="text-5xl mb-3">📂</p>
                  <p className="text-gray-300 font-medium">Drop file here or click to browse</p>
                  <p className="text-gray-600 text-sm mt-1">CSV · Excel · SQLite · SQL · JSON · TSV · Max 50MB</p>
                </div>
              )}
            </div>

            {/* Preview */}
            {preview && !isSqlFile && (
              <div className="mt-4 bg-gray-800 border border-gray-700 rounded-xl p-4">
                <p className="text-xs text-gray-500 uppercase tracking-wider mb-2">Preview</p>
                {preview.columns && (
                  <div>
                    <p className="text-gray-400 text-xs mb-2">
                      ~{preview.total_rows_estimate ?? preview.total_rows ?? '?'} rows ·
                      {' '}{preview.columns.length} columns
                      {preview.delimiter ? ` · delimiter "${preview.delimiter}"` : ''}
                    </p>
                    <div className="overflow-x-auto rounded-lg">
                      <table className="text-xs w-full">
                        <thead className="bg-gray-900">
                          <tr>{preview.columns.slice(0, 7).map(c => (
                            <th key={c} className="text-left text-gray-500 px-3 py-2 whitespace-nowrap">{c}</th>
                          ))}</tr>
                        </thead>
                        <tbody>
                          {(preview.preview_rows || []).slice(0, 4).map((row, i) => (
                            <tr key={i} className="border-t border-gray-800">
                              {row.slice(0, 7).map((cell, j) => (
                                <td key={j} className="text-gray-400 px-3 py-2 max-w-32 truncate">{cell}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
                {preview.tables && <p className="text-gray-400 text-xs">Tables: <span className="text-white">{preview.tables.join(', ')}</span></p>}
                {preview.sheets && <p className="text-gray-400 text-xs">Sheets: <span className="text-white">{preview.sheets.map(s => s.sheet).join(', ')}</span></p>}
              </div>
            )}

            {/* Name + Upload */}
            {uploadFile && (
              <div className="mt-4 flex gap-3 items-end">
                <div className="flex-1">
                  <label className="block text-xs text-gray-400 mb-1.5">Connection Name</label>
                  <input value={uploadName} onChange={e => setUploadName(e.target.value)}
                    placeholder="My dataset"
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2.5 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500" />
                </div>
                <div className="flex gap-2">
                  <button onClick={() => { setUploadFile(null); setUploadName(''); setPreview(null); setFeedback(null) }}
                    className="text-gray-500 hover:text-white px-3 py-2.5 rounded-lg text-sm border border-gray-700 hover:border-gray-500 transition-colors">
                    Clear
                  </button>
                  <button onClick={() => uploadMutation.mutate({ file: uploadFile, name: uploadName })}
                    disabled={!uploadName.trim() || uploadMutation.isPending}
                    className="bg-blue-600 hover:bg-blue-500 disabled:opacity-40 disabled:cursor-not-allowed text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap">
                    {uploadMutation.isPending ? (
                      <span className="flex items-center gap-2">
                        <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        {isSqlFile ? 'Executing...' : 'Uploading...'}
                      </span>
                    ) : isSqlFile ? 'Execute & Connect' : 'Upload & Connect'}
                  </button>
                </div>
              </div>
            )}

            {feedback && (
              <div className={`mt-4 rounded-xl p-4 border ${feedback.ok ? 'bg-green-950 border-green-800' : 'bg-red-950 border-red-800'}`}>
                <p className={`text-sm font-medium ${feedback.ok ? 'text-green-400' : 'text-red-400'}`}>
                  {feedback.ok ? '✓ ' : '✗ '}{feedback.msg}
                </p>
                {feedback.ok && feedback.detail?.tables && (
                  <p className="text-xs text-green-600 mt-1">Tables: {feedback.detail.tables.join(', ')}</p>
                )}
                {feedback.ok && feedback.detail?.table_name && (
                  <p className="text-xs text-green-600 mt-1">
                    Table: {feedback.detail.table_name} · {feedback.detail.rows} rows
                  </p>
                )}
                {feedback.ok && (
                  <Link to="/query" className="text-xs text-green-400 underline mt-2 inline-block hover:text-green-300">
                    Start querying →
                  </Link>
                )}
              </div>
            )}
          </div>
        )}

        {/* Connections list */}
        <div>
          <h2 className="text-white font-semibold mb-3">
            Your Databases
            <span className="text-gray-600 font-normal text-sm ml-2">({connections.length})</span>
          </h2>
          {isLoading ? (
            <div className="text-gray-500 text-sm">Loading...</div>
          ) : connections.length === 0 ? (
            <div className="bg-gray-900 border border-gray-800 rounded-xl p-12 text-center">
              <p className="text-5xl mb-3">🗄️</p>
              <p className="text-gray-400 font-medium">No databases yet</p>
              <p className="text-gray-600 text-sm mt-1">Upload a file or connect a database above</p>
            </div>
          ) : (
            <div className="space-y-2">
              {connections.map(conn => {
                const icon = conn.db_type === 'postgres' ? '🐘'
                  : conn.db_type === 'mysql' ? '🐬'
                  : conn.db_type === 'mssql' ? '🪟'
                  : '📁'
                return (
                  <div key={conn.id}
                    className="bg-gray-900 border border-gray-800 hover:border-gray-600 rounded-xl px-4 py-4 flex items-center gap-4 transition-colors">
                    <div className="w-10 h-10 rounded-xl bg-gray-800 flex items-center justify-center text-xl shrink-0">
                      {icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-white font-medium text-sm">{conn.name}</p>
                      <p className="text-gray-600 text-xs mt-0.5">
                        {conn.db_type} · Added {new Date(conn.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <Link to={`/query/${conn.id}`}
                        className="bg-blue-600 hover:bg-blue-500 text-white px-4 py-1.5 rounded-lg text-xs font-medium transition-colors">
                        Query →
                      </Link>
                      <button
                        onClick={() => { if (window.confirm(`Delete "${conn.name}"?`)) deleteMutation.mutate(conn.id) }}
                        className="text-gray-700 hover:text-red-400 transition-colors text-xs px-2 py-1.5 rounded hover:bg-gray-800">
                        Delete
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>
    </AppShell>
  )
}