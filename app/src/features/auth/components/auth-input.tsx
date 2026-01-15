import type { ComponentProps } from "react"

import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { cn } from "@/lib/utils"

interface AuthInputProps extends ComponentProps<typeof Input> {
  label: string
  error?: string
  required?: boolean
}

export function AuthInput({
  label,
  error,
  required,
  className,
  ...props
}: AuthInputProps) {
  return (
    <div className="space-y-2">
      <Label htmlFor={props.id}>
        {label}
        {required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Input
        {...props}
        className={cn(
          error && "border-destructive focus-visible:ring-destructive/20",
          className,
        )}
        aria-invalid={!!error}
      />
      {error && (
        <p className="text-sm text-destructive font-medium" role="alert">
          {error}
        </p>
      )}
    </div>
  )
}
