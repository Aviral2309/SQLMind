import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import api from '../utils/api'

export const useAuthStore = create(
  persist(
    (set, get) => ({
      token: null,
      refreshToken: null,
      user: null,
      loading: false,
      error: null,

      login: async (email, password) => {
        set({ loading: true, error: null })
        try {
          const res = await api.post('/auth/login', { email, password })
          const { access_token, refresh_token } = res.data
          const payload = JSON.parse(atob(access_token.split('.')[1]))
          set({ token: access_token, refreshToken: refresh_token,
                user: { id: payload.sub, email: payload.email }, loading: false })
          return true
        } catch (err) {
          set({ error: err.response?.data?.detail || 'Login failed', loading: false })
          return false
        }
      },

      register: async (email, username, password) => {
        set({ loading: true, error: null })
        try {
          const res = await api.post('/auth/register', { email, username, password })
          const { access_token, refresh_token } = res.data
          const payload = JSON.parse(atob(access_token.split('.')[1]))
          set({ token: access_token, refreshToken: refresh_token,
                user: { id: payload.sub, email: payload.email }, loading: false })
          return true
        } catch (err) {
          set({ error: err.response?.data?.detail || 'Registration failed', loading: false })
          return false
        }
      },

      logout: async () => {
        const { refreshToken } = get()
        try {
          if (refreshToken) await api.post('/auth/logout', { refresh_token: refreshToken })
        } catch {}
        set({ token: null, refreshToken: null, user: null })
      },

      clearError: () => set({ error: null }),
    }),
    {
      name: 'sqlmind-auth',
      partialize: (s) => ({ token: s.token, refreshToken: s.refreshToken, user: s.user }),
    }
  )
)
