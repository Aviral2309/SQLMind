import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuthStore } from '../stores/authStore'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPass, setShowPass] = useState(false)
  const { login, loading, error, clearError } = useAuthStore()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    clearError()
    const ok = await login(email, password)
    if (ok) navigate('/dashboard')
  }

  return (
    <div className="min-h-screen bg-gray-950 flex">
      {/* Left — branding */}
      <div className="hidden lg:flex flex-col justify-between w-1/2 bg-gradient-to-br from-gray-900 to-gray-950 border-r border-gray-800 p-12">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">S</div>
          <span className="font-bold text-lg text-white">SQL<span className="text-blue-400">Mind</span></span>
        </div>
        <div>
          <h2 className="text-4xl font-bold text-white mb-4 leading-tight">
            Your data,<br />
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-400 to-purple-400">
              answered instantly
            </span>
          </h2>
          <p className="text-gray-400 text-lg leading-relaxed mb-8">
            Ask any question about your database in plain English. 
            SQLMind handles the SQL — you get the answers.
          </p>
          <div className="space-y-3">
            {["Natural language → SQL → Results", "Auto-generated BI dashboards", "Anomaly detection & insights"].map(f => (
              <div key={f} className="flex items-center gap-3 text-gray-400 text-sm">
                <span className="w-5 h-5 bg-blue-600/20 border border-blue-600/30 rounded-full flex items-center justify-center text-blue-400 text-xs">✓</span>
                {f}
              </div>
            ))}
          </div>
        </div>
        <p className="text-gray-700 text-xs">AI-Powered Data Intelligence Platform</p>
      </div>

      {/* Right — form */}
      <div className="flex-1 flex items-center justify-center px-6">
        <div className="w-full max-w-sm">
          <div className="lg:hidden flex items-center gap-2 justify-center mb-8">
            <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center font-bold text-sm">S</div>
            <span className="font-bold text-lg text-white">SQL<span className="text-blue-400">Mind</span></span>
          </div>

          <h1 className="text-2xl font-bold text-white mb-1">Welcome back</h1>
          <p className="text-gray-500 text-sm mb-7">Sign in to your account</p>

          {error && (
            <div className="bg-red-950/50 border border-red-800 rounded-xl px-4 py-3 mb-5">
              <p className="text-red-400 text-sm">{error}</p>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Email</label>
              <input type="email" value={email} onChange={e => setEmail(e.target.value)}
                placeholder="you@company.com" required
                className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors" />
            </div>
            <div>
              <label className="block text-xs text-gray-400 mb-1.5">Password</label>
              <div className="relative">
                <input type={showPass ? 'text' : 'password'} value={password} onChange={e => setPassword(e.target.value)}
                  placeholder="••••••••" required
                  className="w-full bg-gray-900 border border-gray-700 rounded-xl px-4 py-3 pr-10 text-white text-sm placeholder-gray-600 focus:outline-none focus:border-blue-500 transition-colors" />
                <button type="button" onClick={() => setShowPass(p => !p)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white text-xs transition-colors">
                  {showPass ? '🙈' : '👁️'}
                </button>
              </div>
            </div>
            <button type="submit" disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white font-semibold py-3 rounded-xl text-sm transition-all hover:scale-[1.02] active:scale-[0.98]">
              {loading ? 'Signing in...' : 'Sign in →'}
            </button>
          </form>

          <p className="text-center text-gray-600 text-sm mt-6">
            No account?{' '}
            <Link to="/register" className="text-blue-400 hover:text-blue-300 font-medium">Create one free</Link>
          </p>
          <p className="text-center mt-3">
            <Link to="/" className="text-gray-700 hover:text-gray-500 text-xs transition-colors">← Back to home</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
