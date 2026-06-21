const NODE_CONFIG = {
  orchestrator: { icon: '🎯', label: 'Orchestrator', color: 'border-purple-700 bg-purple-950/50' },
  schema_agent:  { icon: '🗂️', label: 'Schema Agent',  color: 'border-blue-700 bg-blue-950/50' },
  sql_generator: { icon: '⚡', label: 'SQL Generator', color: 'border-green-700 bg-green-950/50' },
  verifier:      { icon: '🔍', label: 'Verifier',      color: 'border-yellow-700 bg-yellow-950/50' },
  explainer:     { icon: '💬', label: 'Explainer',     color: 'border-teal-700 bg-teal-950/50' },
}

function StepDetail({ node, data }) {
  if (!data) return null
  switch (node) {
    case 'orchestrator':
      return <p className="text-xs text-gray-400 mt-1">Score: <span className={data.guardrail_score > 0.5 ? 'text-red-400' : 'text-green-400'}>{data.guardrail_score?.toFixed(2) ?? '0.00'}</span></p>
    case 'schema_agent':
      return <p className="text-xs text-gray-400 mt-1">{data.table_count ?? 0} tables · {data.rag_chunks_used ?? 0} RAG chunks</p>
    case 'sql_generator':
      return <p className="text-xs text-gray-400 mt-1">Iteration {data.iteration} · {data.tokens_used ?? 0} tokens</p>
    case 'verifier':
      return <div className="text-xs mt-1 space-y-0.5">
        <p><span className={data.passed ? 'text-green-400' : 'text-red-400'}>{data.passed ? '✓ syntax' : '✗ syntax'}</span>{' · '}<span className={data.safety_passed ? 'text-green-400' : 'text-red-400'}>{data.safety_passed ? '✓ safe' : '✗ unsafe'}</span></p>
        {data.hallucination_score > 0 && <p className="text-orange-400">Hallucination: {(data.hallucination_score * 100).toFixed(0)}%</p>}
        {data.errors?.[0] && <p className="text-red-400 truncate">{data.errors[0]}</p>}
      </div>
    case 'explainer':
      return <p className="text-xs text-green-400 mt-1">✓ Done</p>
    default: return null
  }
}

export default function AgentStepViewer({ steps, status }) {
  return (
    <div className="bg-gray-950 border border-gray-800 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-xs text-gray-500 uppercase tracking-wider font-medium">Agent trace</span>
        {status === 'running' && <span className="flex gap-0.5">{[0,1,2].map(i => <span key={i} className="w-1 h-1 rounded-full bg-blue-400 animate-bounce" style={{ animationDelay: `${i*0.15}s` }} />)}</span>}
      </div>
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
        {Object.entries(NODE_CONFIG).map(([nodeName, cfg]) => {
          const step = steps.find(s => s.node === nodeName)
          const isActive = step && steps[steps.length-1]?.node === nodeName && status === 'running'
          return (
            <div key={nodeName} className={`border rounded-lg p-3 transition-all duration-300 ${step ? cfg.color : 'border-gray-800 bg-gray-900/30 opacity-40'} ${isActive ? 'ring-1 ring-blue-500' : ''}`}>
              <div className="flex items-center gap-1.5">
                <span className="text-sm">{cfg.icon}</span>
                <span className="text-xs font-medium text-white">{cfg.label}</span>
              </div>
              {step && <StepDetail node={nodeName} data={step.data} />}
            </div>
          )
        })}
      </div>
    </div>
  )
}
