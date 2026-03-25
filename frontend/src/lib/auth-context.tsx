'use client'

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'

interface AuthState {
  token: string | null
  userId: string | null
  email: string | null
  isLoading: boolean
}

interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({
    token: null,
    userId: null,
    email: null,
    isLoading: true,
  })

  useEffect(() => {
    const token = localStorage.getItem('verity_token')
    const email = localStorage.getItem('verity_email')
    if (token) {
      setState({ token, userId: null, email, isLoading: false })
    } else {
      setState(s => ({ ...s, isLoading: false }))
    }
  }, [])

  const login = async (email: string, password: string) => {
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const resp = await fetch(
      `${API}/auth/login?email=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`,
      { method: 'POST' }
    )
    if (!resp.ok) throw new Error('Invalid credentials')
    const data = await resp.json()
    localStorage.setItem('verity_token', data.access_token)
    localStorage.setItem('verity_email', email)
    setState({ token: data.access_token, userId: null, email, isLoading: false })
  }

  const logout = () => {
    localStorage.removeItem('verity_token')
    localStorage.removeItem('verity_email')
    setState({ token: null, userId: null, email: null, isLoading: false })
  }

  return (
    <AuthContext.Provider value={{ ...state, login, logout, isAuthenticated: !!state.token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
