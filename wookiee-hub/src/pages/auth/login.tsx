import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { supabase } from "@/lib/supabase"
import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { PageHeader } from "@/components/layout/page-header"

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
        <PageHeader
          kicker="Wookiee"
          title="Войти"
          description="Доступ только для сотрудников из Bitrix24"
        />

        <div className="bg-card border border-border rounded-xl p-6 space-y-4">
          {mode === "magic" ? (
            <form onSubmit={handleMagicLink} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="email" className="text-sm font-medium text-foreground">
                  Email
                </label>
                <Input
                  id="email"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@wookiee.shop"
                />
                <p className="text-xs text-muted-foreground">
                  Введите рабочий email — пришлём magic-link.
                </p>
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}
              {success && <p className="text-sm text-emerald-600">{success}</p>}

              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Отправляю..." : "Получить ссылку для входа"}
              </Button>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setMode("password")
                  setError(null)
                  setSuccess(null)
                }}
                className="w-full text-xs text-muted-foreground"
              >
                Войти с паролем
              </Button>
            </form>
          ) : (
            <form onSubmit={handlePassword} className="space-y-4">
              <div className="space-y-1.5">
                <label htmlFor="email-pwd" className="text-sm font-medium text-foreground">
                  Email
                </label>
                <Input
                  id="email-pwd"
                  type="email"
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@wookiee.shop"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="text-sm font-medium text-foreground">
                  Пароль
                </label>
                <Input
                  id="password"
                  type="password"
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
              </div>

              {error && <p className="text-sm text-destructive">{error}</p>}

              <Button type="submit" disabled={loading} className="w-full">
                {loading ? "Вхожу..." : "Войти"}
              </Button>

              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setMode("magic")
                  setError(null)
                }}
                className="w-full text-xs text-muted-foreground"
              >
                Назад к магическим ссылкам
              </Button>
            </form>
          )}
        </div>
      </div>
    </div>
  )
}
