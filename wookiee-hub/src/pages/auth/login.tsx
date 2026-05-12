import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { Mail, Lock } from "lucide-react"
import { supabase } from "@/lib/supabase"
import { Button } from "@/components/ui-v2/primitives"
import { TextField } from "@/components/ui-v2/forms"
import { Alert } from "@/components/ui-v2/feedback"

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
    <div className="min-h-screen flex items-center justify-center bg-page px-4">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <h1 className="text-4xl text-primary">
            <span className="font-serif italic">Wookiee</span>
            <span className="font-sans ml-2 text-secondary">Hub</span>
          </h1>
          <p className="text-sm text-muted mt-2">Войдите в рабочее пространство</p>
        </div>

        <div className="bg-elevated border border-default rounded-xl p-6 space-y-4 shadow-sm">
          {mode === "magic" ? (
            <form onSubmit={handleMagicLink} className="space-y-4">
              <TextField
                id="email"
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                required
                autoComplete="email"
                placeholder="you@wookiee.shop"
                hint="Доступ только для сотрудников из Bitrix24."
                prefix={Mail}
                disabled={loading}
              />

              {error && <Alert variant="danger" description={error} />}
              {success && <Alert variant="success" description={success} />}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                disabled={!email}
                className="w-full"
              >
                {loading ? "Отправляю…" : "Получить ссылку для входа"}
              </Button>

              <button
                type="button"
                onClick={() => {
                  setMode("password")
                  setError(null)
                  setSuccess(null)
                }}
                className="w-full text-xs text-muted hover:text-secondary transition-colors"
              >
                Войти с паролем
              </button>
            </form>
          ) : (
            <form onSubmit={handlePassword} className="space-y-4">
              <TextField
                id="email-pwd"
                label="Email"
                type="email"
                value={email}
                onChange={setEmail}
                required
                autoComplete="email"
                placeholder="you@wookiee.shop"
                prefix={Mail}
                disabled={loading}
              />

              <TextField
                id="password"
                label="Пароль"
                type="password"
                value={password}
                onChange={setPassword}
                required
                autoComplete="current-password"
                prefix={Lock}
                disabled={loading}
              />

              {error && <Alert variant="danger" description={error} />}

              <Button
                type="submit"
                variant="primary"
                size="lg"
                loading={loading}
                disabled={!email || !password}
                className="w-full"
              >
                {loading ? "Вхожу…" : "Войти"}
              </Button>

              <button
                type="button"
                onClick={() => {
                  setMode("magic")
                  setError(null)
                }}
                className="w-full text-xs text-muted hover:text-secondary transition-colors"
              >
                Назад к ссылкам по email
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
