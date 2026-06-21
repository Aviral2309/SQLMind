import axios from 'axios'

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { 'Content-Type': 'application/json' },
})

// Request interceptor — attach token
api.interceptors.request.use((config) => {
  const stored = localStorage.getItem('sqlmind-auth')
  if (stored) {
    const { state } = JSON.parse(stored)
    if (state?.token) {
      config.headers.Authorization = `Bearer ${state.token}`
    }
  }
  return config
})

// Response interceptor — auto refresh on 401
api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config
    if (error.response?.status === 401 && !original._retry) {
      original._retry = true
      try {
        const stored = localStorage.getItem('sqlmind-auth')
        if (stored) {
          const { state } = JSON.parse(stored)
          if (state?.refreshToken) {
            const res = await axios.post(`${API_URL}/api/v1/auth/refresh`, {
              refresh_token: state.refreshToken,
            })
            const { access_token, refresh_token } = res.data
            // Update stored tokens
            const parsed = JSON.parse(stored)
            parsed.state.token = access_token
            parsed.state.refreshToken = refresh_token
            localStorage.setItem('sqlmind-auth', JSON.stringify(parsed))
            original.headers.Authorization = `Bearer ${access_token}`
            return api(original)
          }
        }
      } catch {
        localStorage.removeItem('sqlmind-auth')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
