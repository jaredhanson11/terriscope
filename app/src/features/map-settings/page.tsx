import {
  IconAlertTriangle,
  IconCheck,
  IconChevronLeft,
  IconClock,
  IconLoader2,
  IconPlus,
  IconTrash,
  IconUserX,
} from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import { useState } from "react"
import { useNavigate, useParams } from "react-router-dom"

import { useMe } from "@/app/providers/me-provider/context"
import { AppRoutes, PageName } from "@/app/routes"
import { PageLayout } from "@/components/layout"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogMedia,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import {
  useCreateMapInviteMutation,
  useRemoveMapMemberMutation,
  useRenameMapMutation,
  useRevokeMapInviteMutation,
} from "@/queries/mutations"
import { queries } from "@/queries/queries"
import { cn } from "@/lib/utils"

function getInitials(name: string | null, email: string): string {
  if (name?.trim()) {
    return name
      .trim()
      .split(/\s+/)
      .map((w) => w[0])
      .join("")
      .toUpperCase()
      .slice(0, 2)
  }
  return email[0].toUpperCase()
}

export default function MapSettingsPage() {
  const { mapId } = useParams<{ mapId: string }>()
  const navigate = useNavigate()
  const me = useMe()

  const mapQuery = useQuery(queries.getMap(mapId!))
  const membersQuery = useQuery(queries.listMapMembers(mapId!))
  const invitesQuery = useQuery(queries.listMapInvites(mapId!))

  const renameMutation = useRenameMapMutation()
  const removeMemberMutation = useRemoveMapMemberMutation()
  const createInviteMutation = useCreateMapInviteMutation()
  const revokeInviteMutation = useRevokeMapInviteMutation()

  const [mapName, setMapName] = useState<string | null>(null)
  const [nameSaved, setNameSaved] = useState(false)

  const [inviteEmail, setInviteEmail] = useState("")

  const resolvedName = mapName ?? mapQuery.data?.name ?? ""
  const isOwner =
    membersQuery.data?.find((m) => m.user_id === me.id)?.role === "OWNER"

  function handleSaveName() {
    if (!mapId || !resolvedName.trim()) return
    setNameSaved(false)
    renameMutation.mutate(
      { mapId, name: resolvedName },
      {
        onSuccess: () => {
          setNameSaved(true)
          setTimeout(() => setNameSaved(false), 3000)
        },
      },
    )
  }

  function handleRemoveMember(userId: number) {
    if (!mapId) return
    removeMemberMutation.mutate({ mapId, userId })
  }

  function handleInvite() {
    if (!mapId || !inviteEmail.trim()) return
    createInviteMutation.mutate(
      { mapId, email: inviteEmail.trim() },
      { onSuccess: () => setInviteEmail("") },
    )
  }

  function handleRevokeInvite(inviteId: number) {
    if (!mapId) return
    revokeInviteMutation.mutate({ mapId, inviteId })
  }

  function handleDeleteMap() {
    // TODO: call delete map mutation, then navigate to maps list
    void navigate(AppRoutes.getRoute(PageName.Home, { mapId: mapId! }))
  }

  function handleBack() {
    void navigate(AppRoutes.getRoute(PageName.Home, { mapId: mapId! }))
  }

  const members = membersQuery.data ?? []
  const invites = invitesQuery.data ?? []
  const collaboratorsLoading = membersQuery.isLoading || invitesQuery.isLoading

  return (
    <PageLayout>
      <PageLayout.FullScreenBody>
        <div className="flex min-h-screen flex-col bg-background">
          <div className="flex items-center gap-3 border-b border-border px-6 py-4">
            <button
              onClick={handleBack}
              className="flex items-center gap-1 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              <IconChevronLeft className="size-4" />
              Back
            </button>
            <Separator orientation="vertical" className="h-4" />
            <h1 className="text-lg font-semibold">Map Settings</h1>
          </div>

          <div className="flex flex-1 justify-center px-4 py-10">
            <div className="w-full max-w-lg space-y-8">
              {/* General */}
              <section>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  General
                </h2>
                <div className="space-y-4 rounded-xl border border-border bg-card p-6">
                  <div className="space-y-1.5">
                    <Label htmlFor="map-name">Map name</Label>
                    {mapQuery.isLoading ? (
                      <Skeleton className="h-9 w-full" />
                    ) : (
                      <Input
                        id="map-name"
                        value={resolvedName}
                        onChange={(e) => {
                          setMapName(e.target.value)
                          setNameSaved(false)
                        }}
                        placeholder="My territory map"
                        disabled={!isOwner}
                      />
                    )}
                  </div>
                  {isOwner && (
                    <div className="flex items-center gap-3">
                      <Button
                        onClick={handleSaveName}
                        disabled={
                          renameMutation.isPending || !resolvedName.trim()
                        }
                      >
                        {renameMutation.isPending ? (
                          <>
                            <IconLoader2 className="mr-2 size-4 animate-spin" />
                            Saving…
                          </>
                        ) : nameSaved ? (
                          <>
                            <IconCheck className="mr-2 size-4" />
                            Saved
                          </>
                        ) : (
                          "Save changes"
                        )}
                      </Button>
                      {renameMutation.isError && (
                        <p className="text-sm text-destructive">
                          {renameMutation.error.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </section>

              {/* Collaborators */}
              <section>
                <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  Collaborators
                </h2>
                <div className="overflow-hidden rounded-xl border border-border bg-card">
                  {collaboratorsLoading ? (
                    <div className="divide-y divide-border">
                      {[0, 1, 2].map((i) => (
                        <div key={i} className="flex items-center gap-3 px-6 py-3.5">
                          <Skeleton className="size-8 rounded-full shrink-0" />
                          <div className="flex-1 space-y-1.5">
                            <Skeleton className="h-3.5 w-32" />
                            <Skeleton className="h-3 w-44" />
                          </div>
                          <Skeleton className="h-5 w-16 rounded-full" />
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="divide-y divide-border">
                      {members.map((m) => {
                        const isCurrentUser = m.user_id === me.id
                        return (
                          <div
                            key={m.user_id}
                            className="flex items-center gap-3 px-6 py-3.5"
                          >
                            <Avatar className="size-8 shrink-0">
                              <AvatarFallback className="text-xs">
                                {getInitials(m.name, m.email)}
                              </AvatarFallback>
                            </Avatar>
                            <div className="min-w-0 flex-1">
                              {m.name && (
                                <p className="truncate text-sm font-medium leading-snug">
                                  {m.name}
                                  {isCurrentUser && (
                                    <span className="ml-1.5 font-normal text-muted-foreground">
                                      (you)
                                    </span>
                                  )}
                                </p>
                              )}
                              <p
                                className={cn(
                                  "truncate text-sm",
                                  m.name
                                    ? "text-muted-foreground"
                                    : "font-medium leading-snug",
                                )}
                              >
                                {m.email}
                                {!m.name && isCurrentUser && (
                                  <span className="ml-1.5 font-normal text-muted-foreground">
                                    (you)
                                  </span>
                                )}
                              </p>
                            </div>
                            <Badge
                              variant={m.role === "OWNER" ? "default" : "outline"}
                            >
                              {m.role === "OWNER" ? "Owner" : "Member"}
                            </Badge>
                            {isOwner && !isCurrentUser ? (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
                                onClick={() => handleRemoveMember(m.user_id)}
                                disabled={removeMemberMutation.isPending}
                              >
                                <IconUserX className="size-4" />
                              </Button>
                            ) : (
                              <div className="size-8 shrink-0" />
                            )}
                          </div>
                        )
                      })}

                      {invites.map((inv) => (
                        <div
                          key={inv.id}
                          className="flex items-center gap-3 px-6 py-3.5 opacity-60"
                        >
                          <Avatar className="size-8 shrink-0">
                            <AvatarFallback className="text-xs">
                              {inv.invited_email[0].toUpperCase()}
                            </AvatarFallback>
                          </Avatar>
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium leading-snug">
                              {inv.invited_email}
                            </p>
                          </div>
                          <Badge variant="outline" className="gap-1 text-muted-foreground">
                            <IconClock className="size-3" />
                            Pending
                          </Badge>
                          {isOwner ? (
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8 shrink-0 text-muted-foreground hover:text-destructive"
                              onClick={() => handleRevokeInvite(inv.id)}
                              disabled={revokeInviteMutation.isPending}
                            >
                              <IconUserX className="size-4" />
                            </Button>
                          ) : (
                            <div className="size-8 shrink-0" />
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {isOwner && (
                    <div className="border-t border-border bg-muted/30 px-6 py-4 space-y-3">
                      <p className="text-sm font-medium">Invite collaborator</p>
                      <div className="flex gap-2">
                        <Input
                          type="email"
                          placeholder="colleague@example.com"
                          value={inviteEmail}
                          onChange={(e) => setInviteEmail(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleInvite()
                          }}
                          className="flex-1"
                        />
                        <Button
                          onClick={handleInvite}
                          disabled={
                            !inviteEmail.trim() || createInviteMutation.isPending
                          }
                        >
                          {createInviteMutation.isPending ? (
                            <IconLoader2 className="mr-1.5 size-4 animate-spin" />
                          ) : (
                            <IconPlus className="mr-1.5 size-4" />
                          )}
                          Invite
                        </Button>
                      </div>
                      {createInviteMutation.isError && (
                        <p className="text-sm text-destructive">
                          {createInviteMutation.error.message}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </section>

              {/* Danger Zone — owner only */}
              {isOwner && (
                <section>
                  <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    Danger Zone
                  </h2>
                  <div className="rounded-xl border border-destructive/30 bg-card p-6">
                    <div className="flex items-start justify-between gap-4">
                      <div>
                        <p className="font-medium">Delete this map</p>
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          Permanently removes all layers, nodes, and data. This
                          cannot be undone.
                        </p>
                      </div>
                      <AlertDialog>
                        <AlertDialogTrigger asChild>
                          <Button variant="destructive" className="shrink-0">
                            <IconTrash className="mr-2 size-4" />
                            Delete map
                          </Button>
                        </AlertDialogTrigger>
                        <AlertDialogContent>
                          <AlertDialogHeader>
                            <AlertDialogMedia>
                              <IconAlertTriangle className="text-destructive" />
                            </AlertDialogMedia>
                            <AlertDialogTitle>Delete map?</AlertDialogTitle>
                            <AlertDialogDescription>
                              <strong className="text-foreground">
                                {resolvedName}
                              </strong>{" "}
                              and all its layers, nodes, and data will be
                              permanently deleted. This cannot be undone.
                            </AlertDialogDescription>
                          </AlertDialogHeader>
                          <AlertDialogFooter>
                            <AlertDialogCancel>Cancel</AlertDialogCancel>
                            <AlertDialogAction
                              variant="destructive"
                              onClick={handleDeleteMap}
                            >
                              Delete map
                            </AlertDialogAction>
                          </AlertDialogFooter>
                        </AlertDialogContent>
                      </AlertDialog>
                    </div>
                  </div>
                </section>
              )}
            </div>
          </div>
        </div>
      </PageLayout.FullScreenBody>
    </PageLayout>
  )
}
