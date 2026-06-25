import { Link } from 'react-router-dom'
import { useState, useEffect } from 'react'

const DEMO_QUERIES = [
  "Show me top 10 customers by revenue this month",
  "Why did sales drop in Q3?",
  "Which products have the highest return rate?",
  "Give me a sales overview dashboard",
  "Find anomalies in daily order patterns",
]

const FEATURES = [
  {
    icon: "💬",
    title: "Natural Language Queries",
    desc: "Ask anything in plain English. SQLMind generates, verifies, and executes SQL automatically.",
    color: "from-blue-600/20 to-blue-800/5",
    border: "border-blue-800/50",
  },
  {
    icon: "✨",
    title: "NL-to-Dashboard",
    desc: "One sentence generates a complete multi-panel BI dashboard. No configuration needed.",
    color: "from-purple-600/20 to-purple-800/5",
    border: "border-purple-800/50",
    badge: "UNIQUE",
  },
  {
    icon: "🔍",
    title: "Hallucination Detection",
    desc: "AST-based verification cross-references every generated column and table against your actual schema.",
    color: "from-green-600/20 to-green-800/5",
    border: "border-green-800/50",
  },
  {
    icon: "⚡",
    title: "5-Node Agent Pipeline",
    desc: "Orchestrator → Schema RAG → Generator → Verifier → Explainer. Retries automatically on failure.",
    color: "from-yellow-600/20 to-yellow-800/5",
    border: "border-yellow-800/50",
  },
  {
    icon: "📊",
    title: "Auto Insights",
    desc: "Analyze any database instantly. Trends, anomalies, data quality — no questions needed.",
    color: "from-teal-600/20 to-teal-800/5",
    border: "border-teal-800/50",
  },
  {
    icon: "🔌",
    title: "Connect Anything",
    desc: "PostgreSQL, MySQL, SQLite, CSV, Excel, JSON, SQL files. Upload or connect via URL.",
    color: "from-orange-600/20 to-orange-800/5",
    border: "border-orange-800/50",
  },
]

const STATS = [
  { value: "5-Node", label: "Agent Pipeline" },
  { value: "6+", label: "Database Types" },
  { value: "< 5s", label: "Avg Response" },
  { value: "0", label: "SQL Knowledge Needed" },
]

export default function LandingPage() {
  const [queryIdx, setQueryIdx] = useState(0)
  const [displayed, setDisplayed] = useState('')
  const [typing, setTyping] = useState(true)

  useEffect(() => {
    const query = DEMO_QUERIES[queryIdx]
    let i = 0
    setDisplayed('')
    setTyping(true)

    const typeInterval = setInterval(() => {
      if (i < query.length) {
        setDisplayed(query.slice(0, i + 1))
        i++
      } else {
        clearInterval(typeInterval)
        setTyping(false)
        setTimeout(() => {
          setQueryIdx(prev => (prev + 1) % DEMO_QUERIES.length)
        }, 2000)
      }
    }, 40)

    return () => clearInterval(typeInterval)
  }, [queryIdx])

  return (
    <div className="min-h-screen bg-gray-950 text-white overflow-x-hidden">

      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 border-b border-gray-800/50 bg-gray-950/80 backdrop-blur-xl">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center text-sm font-bold">S</div>
            <span className="font-bold text-lg">SQL<span className="text-blue-400">Mind</span></span>
          </div>
          <div className="flex items-center gap-3">
            <Link to="/login" className="text-gray-400 hover:text-white text-sm transition-colors px-4 py-2">
              Sign in
            </Link>
            <Link to="/register"
              className="bg-blue-600 hover:bg-blue-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
              Get started free
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <div className="pt-32 pb-20 px-6 text-center relative">
        {/* Glow */}
        <div className="absolute top-20 left-1/2 -translate-x-1/2 w-96 h-96 bg-blue-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute top-40 left-1/3 w-64 h-64 bg-purple-600/8 rounded-full blur-3xl pointer-events-none" />

        <div className="relative max-w-4xl mx-auto">
          <div className="inline-flex items-center gap-2 bg-blue-600/10 border border-blue-600/20 rounded-full px-4 py-1.5 text-blue-400 text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-pulse" />
            AI-Powered Data Intelligence Platform
          </div>

          <h1 className="text-5xl md:text-7xl font-bold mb-6 leading-tight tracking-tight">
            Ask your database
            <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
              in plain English
            </span>
          </h1>

          <p className="text-gray-400 text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            SQLMind turns natural language into SQL, executes it, and returns answers — 
            not just queries. Connect any database and start asking questions instantly.
          </p>

          {/* Typewriter demo */}
          <div className="bg-gray-900/80 border border-gray-700 rounded-2xl p-4 max-w-2xl mx-auto mb-8 text-left">
            <div className="flex items-center gap-2 mb-3">
              <div className="w-2 h-2 rounded-full bg-red-500" />
              <div className="w-2 h-2 rounded-full bg-yellow-500" />
              <div className="w-2 h-2 rounded-full bg-green-500" />
              <span className="text-gray-600 text-xs ml-2">SQLMind Query Editor</span>
            </div>
            <p className="text-gray-300 font-mono text-sm min-h-[24px]">
              {displayed}
              {typing && <span className="inline-block w-0.5 h-4 bg-blue-400 ml-0.5 animate-pulse align-middle" />}
            </p>
            <div className="mt-3 pt-3 border-t border-gray-800 flex items-center gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-green-400" />
              <span className="text-green-400 text-xs">Answer generated in 3.2s</span>
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <Link to="/register"
              className="bg-blue-600 hover:bg-blue-500 text-white font-semibold px-8 py-3.5 rounded-xl transition-all hover:scale-105 text-sm">
              Start for free →
            </Link>
            <Link to="/login"
              className="bg-gray-800 hover:bg-gray-700 text-white font-medium px-8 py-3.5 rounded-xl transition-colors text-sm border border-gray-700">
              Sign in
            </Link>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="max-w-4xl mx-auto px-6 mb-24">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {STATS.map(({ value, label }) => (
            <div key={label} className="text-center bg-gray-900/50 border border-gray-800 rounded-2xl p-5">
              <p className="text-3xl font-bold text-white mb-1">{value}</p>
              <p className="text-gray-500 text-sm">{label}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Features */}
      <div className="max-w-6xl mx-auto px-6 mb-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Everything you need for
            <span className="text-blue-400"> data intelligence</span>
          </h2>
          <p className="text-gray-500 max-w-xl mx-auto">
            From simple queries to complex business insights — SQLMind handles it all.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {FEATURES.map(({ icon, title, desc, color, border, badge }) => (
            <div key={title}
              className={`relative bg-gradient-to-br ${color} border ${border} rounded-2xl p-6 hover:scale-[1.02] transition-transform`}>
              {badge && (
                <span className="absolute top-4 right-4 text-xs bg-purple-600 text-white px-2 py-0.5 rounded-full font-medium">
                  {badge}
                </span>
              )}
              <div className="text-3xl mb-4">{icon}</div>
              <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
              <p className="text-gray-400 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* How it works */}
      <div className="max-w-4xl mx-auto px-6 mb-24">
        <div className="text-center mb-12">
          <h2 className="text-3xl font-bold mb-4">How it works</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {[
            { step: "01", title: "Connect", desc: "Upload a file or connect any database — PostgreSQL, MySQL, SQLite, CSV, Excel" },
            { step: "02", title: "Ask", desc: "Type your question in plain English. No SQL knowledge required." },
            { step: "03", title: "Insights", desc: "Get answers, charts, trends, and anomalies — automatically." },
          ].map(({ step, title, desc }) => (
            <div key={step} className="text-center">
              <div className="w-12 h-12 bg-blue-600/20 border border-blue-600/30 rounded-xl flex items-center justify-center text-blue-400 font-bold text-sm mx-auto mb-4">
                {step}
              </div>
              <h3 className="text-white font-semibold text-lg mb-2">{title}</h3>
              <p className="text-gray-500 text-sm leading-relaxed">{desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* CTA */}
      <div className="max-w-3xl mx-auto px-6 mb-24 text-center">
        <div className="bg-gradient-to-br from-blue-600/20 to-purple-600/10 border border-blue-800/40 rounded-3xl p-12">
          <h2 className="text-3xl md:text-4xl font-bold mb-4">
            Ready to talk to your data?
          </h2>
          <p className="text-gray-400 mb-8 max-w-md mx-auto">
            Connect your database and get insights in seconds. No credit card required.
          </p>
          <Link to="/register"
            className="inline-block bg-blue-600 hover:bg-blue-500 text-white font-semibold px-10 py-4 rounded-xl transition-all hover:scale-105 text-base">
            Get started free →
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="border-t border-gray-800 py-8 px-6">
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 bg-blue-600 rounded-md flex items-center justify-center text-xs font-bold">S</div>
            <span className="text-gray-400 text-sm">SQLMind — AI Data Intelligence</span>
          </div>
          <p className="text-gray-600 text-xs">Built with LangGraph · FastAPI · React</p>
        </div>
      </footer>
    </div>
  )
}
