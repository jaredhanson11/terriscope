import { useEffect, useState } from "react"
import type { ReactNode } from "react"

export const VersionsPage = () => {
  const [appVersion, setAppVersion] = useState<string | undefined>(undefined)
  const [appVersionLoading, setAppVersionLoading] = useState(false)

  useEffect(() => {
    function getAppVersion() {
      setAppVersionLoading(true)
      // Need generic fetch because this is a file served statically by the frontend
      fetch("/version.txt")
        .then((response) => {
          if (response.headers.get("content-type") !== "text/plain") {
            setAppVersion(undefined)
          }
          return response.text().then((text) => {
            setAppVersion(text)
          })
        })
        .catch(() => undefined)
        .finally(() => {
          setAppVersionLoading(false)
        })
    }
    getAppVersion()
    const interval = setInterval(getAppVersion, 1000 * 60 * 0.5) // every 30 seconds
    return () => {
      clearInterval(interval)
    }
  }, [])

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-slate-100 dark:from-slate-900 dark:to-slate-800">
      <div className="container mx-auto px-4 py-16 sm:px-6 lg:px-8">
        <div className="max-w-3xl mx-auto">
          {/* Header */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900 dark:text-white mb-2">
              Application Versions
            </h1>
            <p className="text-slate-600 dark:text-slate-400">
              View current deployment information
            </p>
          </div>

          {/* Version Card */}
          <div className="bg-white dark:bg-slate-800 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
            <div className="border-b border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-800/50 px-6 py-4">
              <h2 className="text-xl font-semibold text-slate-900 dark:text-white">
                Frontend Application
              </h2>
            </div>

            <div className="p-6">
              {appVersionLoading ? (
                <Version state="LOADING" />
              ) : appVersion ? (
                <Version state="SUCCESS" version={appVersion} />
              ) : (
                <Version state="ERROR" />
              )}
            </div>
          </div>

          {/* Info Footer */}
          <div className="mt-6 text-center">
            <p className="text-sm text-slate-500 dark:text-slate-400">
              Version information updates automatically every 30 seconds
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

const Version = (
  props: { state: "LOADING" | "ERROR" } | { state: "SUCCESS"; version: string },
) => {
  let version: { line1: ReactNode; line2: string } | undefined = undefined
  if (props.state === "SUCCESS") {
    const commitLine = props.version.split(/\r?\n|\r|\n/g)[0]
    const dateLine = props.version.split(/\r?\n|\r|\n/g)[1]
    const commitLabel = "Commit: "
    if (commitLine.startsWith(commitLabel) && dateLine) {
      const commitHash = commitLine.substring(commitLabel.length)
      version = {
        line1: (
          <div className="flex items-center gap-2 mb-2">
            <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
              {commitLabel}
            </span>
            <a
              href={`https://github.com/jaredhanson11/terriscope/commit/${commitHash}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-mono text-sm text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:underline transition-colors"
            >
              {commitHash.substring(0, 7)}
            </a>
          </div>
        ),
        line2: dateLine,
      }
    }
  }

  return props.state === "SUCCESS" && version ? (
    <div className="space-y-1">
      {version.line1}
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
          Deployed:
        </span>
        <span className="text-sm text-slate-700 dark:text-slate-300">
          {version.line2}
        </span>
      </div>
    </div>
  ) : props.state === "LOADING" ? (
    <div className="flex items-center gap-3">
      <div className="animate-spin rounded-full h-5 w-5 border-2 border-slate-300 border-t-blue-600"></div>
      <span className="text-sm text-slate-600 dark:text-slate-400">
        Loading version information...
      </span>
    </div>
  ) : (
    <div className="flex items-center gap-2 text-red-600 dark:text-red-400">
      <svg
        className="w-5 h-5"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
      <span className="text-sm font-medium">
        Failed to load version information
      </span>
    </div>
  )
}
