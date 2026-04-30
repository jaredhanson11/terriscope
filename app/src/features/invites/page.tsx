import {
  IconCheck,
  IconChevronLeft,
  IconLoader2,
  IconMap,
  IconUserPlus,
  IconX,
} from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useNavigate } from "react-router-dom"

import { useMaps } from "@/app/providers/me-provider/context"
import { AppRoutes, PageName } from "@/app/routes"
import { BrandLogo } from "@/components/brand-logo"
import { PageLayout } from "@/components/layout"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Button } from "@/components/ui/button"
import { Separator } from "@/components/ui/separator"
import {
  useAcceptInviteMutation,
  useDeclineInviteMutation,
} from "@/queries/mutations"
import { queries } from "@/queries/queries"
import type { MapInviteWithMap } from "@/queries/queries"

function InviteCard({
  invite,
  onAccepted,
  onDeclined,
}: {
  invite: MapInviteWithMap
  onAccepted: (mapId: string) => void
  onDeclined: () => void
}) {
  const acceptMutation = useAcceptInviteMutation()
  const declineMutation = useDeclineInviteMutation()

  const inviterLabel = invite.invited_by_name ?? invite.invited_by_email

  function handleAccept() {
    acceptMutation.mutate(invite.id, {
      onSuccess: () => onAccepted(invite.map_id),
    })
  }

  function handleDecline() {
    declineMutation.mutate(invite.id, {
      onSuccess: () => onDeclined(),
    })
  }

  const isBusy = acceptMutation.isPending || declineMutation.isPending

  return (
    <div className="rounded-xl border border-border bg-card p-6 space-y-4">
      <div className="flex items-start gap-4">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-primary/10">
          <IconMap className="size-5 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-semibold truncate">{invite.map_name}</p>
          <p className="text-sm text-muted-foreground mt-0.5">
            Invited by {inviterLabel}
          </p>
        </div>
      </div>

      <Separator />

      <div className="flex gap-2">
        <Button className="flex-1" onClick={handleAccept} disabled={isBusy}>
          {acceptMutation.isPending ? (
            <IconLoader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <IconCheck className="mr-2 size-4" />
          )}
          Accept
        </Button>
        <Button
          variant="outline"
          className="flex-1"
          onClick={handleDecline}
          disabled={isBusy}
        >
          {declineMutation.isPending ? (
            <IconLoader2 className="mr-2 size-4 animate-spin" />
          ) : (
            <IconX className="mr-2 size-4" />
          )}
          Decline
        </Button>
      </div>

      {(acceptMutation.isError || declineMutation.isError) && (
        <p className="text-sm text-destructive">
          {(acceptMutation.error ?? declineMutation.error)?.message}
        </p>
      )}
    </div>
  )
}

export default function InvitesPage() {
  const navigate = useNavigate()
  const maps = useMaps()
  const invitesQuery = useQuery(queries.listMyInvites())

  const invites = invitesQuery.data ?? []
  const hasMaps = maps.length > 0

  // After accept: jump straight to the newly accepted map.
  function handleAccepted(mapId: string) {
    void navigate(AppRoutes.getRoute(PageName.Home, { mapId }))
  }

  // After decline / back / skip: navigate to "/". RootRedirect handles the
  // rest — has-maps users land on their active map; no-maps users get sent
  // to the initialize flow by AuthProvider.
  function handleDeclined() {
    void navigate("/")
  }

  function handleSkip() {
    void navigate(AppRoutes.getRoute(PageName.Initialize))
  }

  function handleBack() {
    void navigate("/")
  }

  return (
    <PageLayout>
      <PageLayout.FullScreenBody>
        <div className="relative flex min-h-screen items-center justify-center bg-background px-4 py-12">
          {hasMaps && (
            <button
              onClick={handleBack}
              className="absolute left-4 top-4 flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <IconChevronLeft className="size-4" />
              Back
            </button>
          )}

          <div className="w-full max-w-md space-y-8">
            <div className="flex flex-col items-center gap-3 text-center">
              <BrandLogo iconOnly iconClassName="h-10 w-auto" />
              <div>
                <h1 className="text-2xl font-semibold">
                  {invites.length > 1
                    ? "You have invitations"
                    : "You have an invitation"}
                </h1>
                <p className="mt-1 text-sm text-muted-foreground">
                  {hasMaps
                    ? "Accept to join, or decline to dismiss."
                    : "Accept to join the map, or skip to create your own."}
                </p>
              </div>
            </div>

            {invitesQuery.isLoading && (
              <div className="flex justify-center py-8">
                <IconLoader2 className="size-6 animate-spin text-muted-foreground" />
              </div>
            )}

            {invitesQuery.isSuccess && invites.length === 0 && (
              <div className="rounded-xl border border-border bg-card p-8 text-center space-y-2">
                <Avatar className="size-12 mx-auto">
                  <AvatarFallback>
                    <IconUserPlus className="size-5 text-muted-foreground" />
                  </AvatarFallback>
                </Avatar>
                <p className="font-medium">No pending invites</p>
                <p className="text-sm text-muted-foreground">
                  All invites have been handled.
                </p>
              </div>
            )}

            <div className="space-y-4">
              {invites.map((invite) => (
                <InviteCard
                  key={invite.id}
                  invite={invite}
                  onAccepted={handleAccepted}
                  onDeclined={handleDeclined}
                />
              ))}
            </div>

            {!hasMaps && (
              <div className="text-center">
                <button
                  onClick={handleSkip}
                  className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline transition-colors"
                >
                  Skip for now — create a new map instead
                </button>
              </div>
            )}
          </div>
        </div>
      </PageLayout.FullScreenBody>
    </PageLayout>
  )
}
