import type { FormEvent, ReactNode } from "react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

interface AuthFormProps {
  onSubmit: (e: FormEvent<HTMLFormElement>) => void
  submitLabel: string
  isLoading?: boolean
  error?: string
  children: ReactNode
  className?: string
}

export function AuthForm({
  onSubmit,
  submitLabel,
  isLoading,
  error,
  children,
  className,
}: AuthFormProps) {
  return (
    <form onSubmit={onSubmit} className={cn("space-y-4", className)}>
      {error && (
        <div className="bg-destructive/10 border border-destructive/30 text-destructive rounded-md p-3 text-sm">
          {error}
        </div>
      )}
      {children}
      <Button type="submit" className="w-full" size="lg" disabled={isLoading}>
        {isLoading ? "Loading..." : submitLabel}
      </Button>
    </form>
  )
}
