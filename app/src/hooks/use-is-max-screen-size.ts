import { useEffect, useState } from "react"

type maxScreenSizeOption = "mobile" | "desktop-xs" | "desktop-sm" | "desktop-md"
export function useIsMaxScreenSize(maxSize: maxScreenSizeOption) {
  const rootStyles = getComputedStyle(document.documentElement)
  const maxSizeString = rootStyles
    .getPropertyValue(`--breakpoint-${maxSize}`)
    .trim()
  const [screenSize, setScreenSize] = useState({
    width: window.innerWidth,
    height: window.innerHeight,
  })

  useEffect(() => {
    const handleResize = () => {
      setScreenSize({
        width: window.innerWidth,
        height: window.innerHeight,
      })
    }
    window.addEventListener("resize", handleResize)
    return () => {
      window.removeEventListener("resize", handleResize)
    }
  }, [])

  return screenSize.width < parseInt(maxSizeString)
}
