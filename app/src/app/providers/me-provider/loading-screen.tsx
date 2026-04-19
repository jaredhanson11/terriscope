import { BrandLogo } from "@/components/brand-logo"
import { Spinner } from "@/components/ui/spinner"

export function AppLoadingScreen() {
  return (
    <div className="fixed inset-0 flex flex-col items-center justify-center bg-linear-to-br from-background via-muted/30 to-background gap-6">
      <BrandLogo iconClassName="h-12" />
      <Spinner className="size-5 text-muted-foreground" />
    </div>
  )
}
