import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { supabase } from '@/lib/supabase'

interface ProtectedRouteProps {
  children: React.ReactNode
}

export function ProtectedRoute({ children }: ProtectedRouteProps) {
  const [status, setStatus] = useState<'loading' | 'auth' | 'unauth'>('loading')

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setStatus(data.session ? 'auth' : 'unauth')
    })

    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setStatus(session ? 'auth' : 'unauth')
    })

    return () => listener.subscription.unsubscribe()
  }, [])

  if (status === 'loading') return null
  if (status === 'unauth') return <Navigate to="/login" replace />
  return <>{children}</>
}
