import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import { PageLayout } from "@/components/layout"
import { useLoginMutation } from "@/queries/mutations"

import { AuthCard, AuthDivider, AuthForm, AuthInput } from "./components"

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [rememberMe, setRememberMe] = useState(false)
  const [formError, setFormError] = useState("")

  const loginMutation = useLoginMutation({
    onSuccess: () => {
      void navigate("/")
    },
    onError: (error) => {
      setFormError(error.message)
    },
  })

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError("")

    if (!email || !password) {
      setFormError("Please fill in all fields")
      return
    }

    loginMutation.mutate({
      email,
      password,
      remember_me: rememberMe,
    })
  }

  return (
    <PageLayout>
      <PageLayout.FullScreenBody>
        <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-background via-muted/30 to-background p-4">
          <AuthCard
            title="Welcome back"
            description="Sign in to your account to continue"
          >
            <AuthForm
              onSubmit={handleSubmit}
              submitLabel="Sign in"
              isLoading={loginMutation.isPending}
              error={formError}
            >
              <AuthInput
                id="email"
                label="Email"
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                }}
                required
                autoComplete="email"
              />
              <AuthInput
                id="password"
                label="Password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                }}
                required
                autoComplete="current-password"
              />
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <input
                    id="remember-me"
                    type="checkbox"
                    checked={rememberMe}
                    onChange={(e) => {
                      setRememberMe(e.target.checked)
                    }}
                    className="h-4 w-4 rounded border-border bg-background text-primary focus:ring-2 focus:ring-ring focus:ring-offset-2"
                  />
                  <label
                    htmlFor="remember-me"
                    className="text-sm font-medium leading-none cursor-pointer select-none"
                  >
                    Remember me
                  </label>
                </div>
                <Link
                  to={"#"}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Forgot password?
                </Link>
              </div>
            </AuthForm>
            <AuthDivider />
            <div className="text-center text-sm">
              <span className="text-muted-foreground">
                Don't have an account?{" "}
              </span>
              <Link
                to={AppRoutes.getRoute(PageName.Register)}
                className="font-medium text-primary hover:underline"
              >
                Sign up
              </Link>
            </div>
          </AuthCard>
        </div>
      </PageLayout.FullScreenBody>
    </PageLayout>
  )
}
