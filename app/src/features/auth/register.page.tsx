import { type FormEvent, useState } from "react"
import { Link, useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import { PageLayout } from "@/components/layout"
import { useRegisterMutation } from "@/queries/mutations"

import { AuthCard, AuthDivider, AuthForm, AuthInput } from "./components"

export default function RegisterPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [formError, setFormError] = useState("")
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})

  const registerMutation = useRegisterMutation({
    onSuccess: () => {
      void navigate("/")
    },
    onError: (error) => {
      setFormError(error.message)
    },
  })

  const validateForm = (): boolean => {
    const errors: Record<string, string> = {}

    if (!email.trim()) {
      errors.email = "Email is required"
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      errors.email = "Invalid email address"
    }

    if (!password) {
      errors.password = "Password is required"
    } else if (password.length < 8) {
      errors.password = "Password must be at least 8 characters"
    }

    if (!confirmPassword) {
      errors.confirmPassword = "Please confirm your password"
    } else if (password !== confirmPassword) {
      errors.confirmPassword = "Passwords do not match"
    }

    setFieldErrors(errors)
    return Object.keys(errors).length === 0
  }

  const handleSubmit = (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setFormError("")
    setFieldErrors({})

    if (!validateForm()) {
      return
    }

    registerMutation.mutate({
      email,
      password,
    })
  }

  return (
    <PageLayout>
      <PageLayout.FullScreenBody>
        <div className="min-h-screen flex items-center justify-center bg-linear-to-br from-background via-muted/30 to-background p-4">
          <AuthCard
            title="Create an account"
            description="Get started with your new account"
          >
            <AuthForm
              onSubmit={handleSubmit}
              submitLabel="Sign up"
              isLoading={registerMutation.isPending}
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
                error={fieldErrors.email}
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
                error={fieldErrors.password}
                required
                autoComplete="new-password"
              />
              <AuthInput
                id="confirm-password"
                label="Confirm password"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => {
                  setConfirmPassword(e.target.value)
                }}
                error={fieldErrors.confirmPassword}
                required
                autoComplete="new-password"
              />
              <div className="text-xs text-muted-foreground pt-2">
                By creating an account, you agree to our{" "}
                <Link to="#" className="text-primary hover:underline">
                  Terms of Service
                </Link>{" "}
                and{" "}
                <Link to="#" className="text-primary hover:underline">
                  Privacy Policy
                </Link>
                .
              </div>
            </AuthForm>
            <AuthDivider />
            <div className="text-center text-sm">
              <span className="text-muted-foreground">
                Already have an account?{" "}
              </span>
              <Link
                to={AppRoutes.getRoute(PageName.Login)}
                className="font-medium text-primary hover:underline"
              >
                Sign in
              </Link>
            </div>
          </AuthCard>
        </div>
      </PageLayout.FullScreenBody>
    </PageLayout>
  )
}
