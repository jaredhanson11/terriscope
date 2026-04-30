import { IconBell, IconChevronRight, IconMail } from "@tabler/icons-react"
import { useQuery } from "@tanstack/react-query"
import type { ReactNode } from "react"
import { useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import { Button } from "@/components/ui/button"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { queries } from "@/queries/queries"
import type { MapInviteWithMap } from "@/queries/queries"

// A single row in the notifications popover. Each notification type (invite,
// job-complete, etc.) gets mapped into this shape so the UI stays uniform.
interface NotificationItem {
  id: string
  icon: ReactNode
  iconBgClass: string
  body: ReactNode
  hint: string
  href: string
}

function inviteToItem(invite: MapInviteWithMap): NotificationItem {
  const inviter = invite.invited_by_name ?? invite.invited_by_email
  return {
    id: `invite-${String(invite.id)}`,
    icon: <IconMail className="size-4 text-primary" />,
    iconBgClass: "bg-primary/10",
    body: (
      <>
        <span className="font-medium">{inviter}</span> invited you to{" "}
        <span className="font-medium">{invite.map_name}</span>
      </>
    ),
    hint: "Review invitation",
    href: AppRoutes.getRoute(PageName.Invites),
  }
}

export function NotificationsBell() {
  const navigate = useNavigate()
  const invitesQuery = useQuery(queries.listMyInvites())

  // Future notification sources (job completions, mentions, etc.) get
  // mapped into NotificationItem and concatenated here.
  const items: NotificationItem[] = (invitesQuery.data ?? []).map(inviteToItem)
  const count = items.length
  const hasUnread = count > 0

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className="relative size-9"
          aria-label={
            hasUnread ? `${String(count)} new notifications` : "Notifications"
          }
        >
          <IconBell className="size-4" />
          {hasUnread && (
            <span className="absolute right-1.5 top-1.5 flex size-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-primary/60" />
              <span className="relative inline-flex size-2 rounded-full bg-primary" />
            </span>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <p className="text-sm font-semibold">Notifications</p>
          {hasUnread && (
            <span className="text-xs text-muted-foreground">
              {count} new
            </span>
          )}
        </div>

        <div className="max-h-80 overflow-y-auto">
          {!hasUnread ? (
            <div className="flex flex-col items-center gap-1 px-4 py-8 text-center">
              <div className="mb-1 flex size-10 items-center justify-center rounded-full bg-muted">
                <IconBell className="size-5 text-muted-foreground" />
              </div>
              <p className="text-sm font-medium">All caught up</p>
              <p className="text-xs text-muted-foreground">
                You'll see updates and invitations here.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-border">
              {items.map((item) => (
                <button
                  key={item.id}
                  onClick={() => void navigate(item.href)}
                  className="flex w-full items-start gap-3 px-4 py-3 text-left transition-colors hover:bg-muted/50"
                >
                  <div
                    className={`flex size-8 shrink-0 items-center justify-center rounded-lg ${item.iconBgClass}`}
                  >
                    {item.icon}
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm leading-snug">{item.body}</p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {item.hint}
                    </p>
                  </div>
                  <IconChevronRight className="mt-0.5 size-4 shrink-0 text-muted-foreground" />
                </button>
              ))}
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
