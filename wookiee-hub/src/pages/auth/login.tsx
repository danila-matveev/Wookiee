import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { supabase } from "@/lib/supabase"

type Mode = "magic" | "password"

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL ?? ""
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY ?? ""

export function LoginPage() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<Mode>("magic")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleMagicLink(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setLoading(true)

    try {
      const checkRes = await fetch(`${SUPABASE_URL}/functions/v1/auth-check-team`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          apikey: SUPABASE_ANON_KEY,
          Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
        },
        body: JSON.stringify({ email }),
      })
      const check = (await checkRes.json()) as { allowed?: boolean; reason?: string }

      if (!checkRes.ok || !check.allowed) {
        setError(check.reason ?? "Этот email не из команды Wookiee")
        return
      }

      const { error: otpError } = await supabase.auth.signInWithOtp({
        email,
        options: {
          shouldCreateUser: true,
          emailRedirectTo: window.location.origin,
        },
      })

      if (otpError) {
        setError("Не удалось отправить ссылку. Попробуйте ещё раз.")
        return
      }
      setSuccess(`Ссылка для входа отправлена на ${email}. Проверь почту.`)
    } catch {
      setError("Сеть недоступна или сервис не отвечает.")
    } finally {
      setLoading(false)
    }
  }

  async function handlePassword(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setSuccess(null)
    setLoading(true)

    const { error: authError } = await supabase.auth.signInWithPassword({ email, password })

    setLoading(false)
    if (authError) {
      setError("Неверный логин или пароль")
      return
    }
    navigate("/operations/tools")
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold text-foreground">Wookiee Hub</h1>
          <p className="text-sm text-muted-foreground mt-1">Войдите в рабочее пространство</p>
        </div>

        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          {mode === "magic" ? (
            <form onSubmit={handleMagicLink} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="you@wookiee.shop"
                />
                <p className="text-xs text-muted-foreground">
                  Доступ только для сотрудников из Bitrix24.
                </p>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
              {success && <p className="text-sm text-emerald-600">{success}</p>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 px-4 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? "Отправляю..." : "Получить ссылку для входа"}
              </button>

              <button
                type="button"
                onClick={() => {
                  setMode("password")
                  setError(null)
                  setSuccess(null)
                }}
                className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Войти с паролем
              </button>
            </form>
          ) : (
            <form onSubmit={handlePassword} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="email-pwd" className="text-sm font-medium text-foreground">
                  Email
                </label>
                <input
                  id="email-pwd"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  placeholder="you@wookiee.shop"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium text-foreground">
                  Пароль
                </label>
                <input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 text-sm border border-border rounded-lg bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                />
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2 px-4 bg-primary text-primary-foreground text-sm font-medium rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50"
              >
                {loading ? "Вхожу..." : "Войти"}
              </button>

              <button
                type="button"
                onClick={() => {
                  setMode("magic")
                  setError(null)
                }}
                className="w-full text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                Назад к магическим ссылкам
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
