import * as React from "react"

import { cn } from "@/lib/utils"

import { Sidebar } from "./ui/sidebar"

interface PageLayoutProps {
  children: React.ReactNode
  className?: string
}

interface LayoutSubComponentProps {
  children: React.ReactNode
  className?: string
}

export function PageLayout({ children, className }: PageLayoutProps) {
  const childArray = React.Children.toArray(children)

  const hasSideBar = childArray.some(
    (child) => React.isValidElement(child) && child.type === PageLayout.SideNav,
  )
  const hasTopNav = childArray.some(
    (child) => React.isValidElement(child) && child.type === PageLayout.TopNav,
  )

  return (
    <div
      className={cn("flex h-screen w-full flex-col overflow-hidden", className)}
    >
      <div className="flex flex-1 overflow-hidden">
        {hasSideBar && (
          <aside className="border-border flex-shrink-0 border-r">
            {childArray.find(
              (child) =>
                React.isValidElement(child) &&
                child.type === PageLayout.SideNav,
            )}
          </aside>
        )}
        <div className="flex flex-1 flex-col overflow-hidden">
          {hasTopNav && (
            <header className="border-border flex-shrink-0 border-b">
              {childArray.find(
                (child) =>
                  React.isValidElement(child) &&
                  child.type === PageLayout.TopNav,
              )}
            </header>
          )}
          <main className="flex-1 overflow-hidden">
            {childArray.find(
              (child) =>
                React.isValidElement(child) &&
                (child.type === PageLayout.ScrollableBody ||
                  child.type === PageLayout.FullScreenBody),
            )}
          </main>
        </div>
      </div>
    </div>
  )
}

PageLayout.SideNav = ({ children }: LayoutSubComponentProps) => {
  const childCount = React.Children.count(children)
  const childArray = React.Children.toArray(children)
  if (
    childCount == 1 ||
    (React.isValidElement(childArray[0]) && childArray[0].type === Sidebar)
  ) {
    return children
  } else {
    throw Error(
      "SideNav only accepts a single child, which must be a shadcn SideBar",
    )
  }
}

PageLayout.TopNav = ({ children, className }: LayoutSubComponentProps) => (
  <div className={cn("flex h-16 items-center px-4", className)}>{children}</div>
)

PageLayout.ScrollableBody = ({
  children,
  className,
}: LayoutSubComponentProps) => (
  <div className={cn("h-full overflow-y-auto", className)}>{children}</div>
)

PageLayout.FullScreenBody = ({
  children,
  className,
}: LayoutSubComponentProps) => (
  <div className={cn("h-full w-full", className)}>{children}</div>
)
