import {
  IconCheck,
  IconChevronDown,
  IconHome,
  IconInfoCircle,
  IconMoon,
  IconPlus,
  IconSettings,
  IconSun,
  IconTrash,
} from "@tabler/icons-react"
import * as React from "react"

import { AppRoutes } from "@/app/routes"
import Logo from "@/assets/logoipsum.svg?react"
import { PageLayout } from "@/components/layout"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenuButton,
  SidebarTrigger,
} from "@/components/ui/sidebar"
import { Map } from "@/features/home/components/map"

// Placeholder data - will be replaced with real data from API
const PROJECTS = [
  {
    id: 1,
    name: "North America",
    lastEdited: "2h ago",
  },
  {
    id: 2,
    name: "EMEA Sales Regions",
    lastEdited: "1d ago",
  },
  {
    id: 3,
    name: "APAC Distribution Areas",
    lastEdited: "3d ago",
  },
  {
    id: 4,
    name: "US Service Zones",
    lastEdited: "1w ago",
  },
]

const LAYERS = [
  { id: "zip_codes", name: "Zip Codes", visible: true },
  { id: "territories", name: "Territories", visible: true },
  { id: "regions", name: "Regions", visible: true },
  { id: "areas", name: "Areas", visible: false },
]

const BASE_MAPS = [
  { id: "osm", name: "OpenStreetMap" },
  { id: "satellite", name: "Satellite" },
  { id: "terrain", name: "Terrain" },
  { id: "dark", name: "Dark" },
  { id: "none", name: "None" },
]

const OVERLAYS = [
  { id: "traffic", name: "Traffic" },
  { id: "transit", name: "Transit Lines" },
  { id: "bicycling", name: "Bike Paths" },
  { id: "demographics", name: "Demographics" },
  { id: "weather", name: "Weather" },
]

export default function HomePage() {
  const currentProject = PROJECTS[0]
  const [isDark, setIsDark] = React.useState(
    document.documentElement.classList.contains("dark"),
  )
  const [baseMap, setBaseMap] = React.useState<
    "osm" | "satellite" | "terrain" | "dark" | "none"
  >("osm")
  const [visibleLayers, setVisibleLayers] = React.useState<
    Record<string, boolean>
  >(LAYERS.reduce((acc, layer) => ({ ...acc, [layer.id]: layer.visible }), {}))

  const toggleTheme = () => {
    const newTheme = !isDark
    setIsDark(newTheme)
    if (newTheme) {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }

  const toggleLayerVisibility = (layerId: string) => {
    setVisibleLayers((prev) => ({ ...prev, [layerId]: !prev[layerId] }))
  }

  return (
    <PageLayout>
      <PageLayout.SideNav>
        <Sidebar>
          <SidebarHeader className="border-border border-b p-4 gap-4">
            <Logo className="h-8" />
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <SidebarMenuButton className="h-auto w-full py-2">
                  <div className="flex w-full items-center gap-3">
                    <IconHome className="h-5 w-5 shrink-0" />
                    <div className="flex-1 text-left">
                      <div className="text-sm font-medium leading-tight">
                        {currentProject.name}
                      </div>
                      <div className="text-muted-foreground text-xs">
                        Last edited {currentProject.lastEdited}
                      </div>
                    </div>
                    <IconChevronDown className="h-4 w-4 shrink-0" />
                  </div>
                </SidebarMenuButton>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="start"
                className="w-(--radix-popper-anchor-width)"
              >
                <DropdownMenuLabel>Recent Maps</DropdownMenuLabel>
                {PROJECTS.map((project) => (
                  <DropdownMenuItem key={project.id} className="gap-3">
                    <IconHome className="h-4 w-4" />
                    <div className="flex-1">
                      <div className="text-sm font-medium">{project.name}</div>
                      <div className="text-muted-foreground text-xs">
                        Last edited {project.lastEdited}
                      </div>
                    </div>
                    {project.id === currentProject.id && (
                      <IconCheck className="h-4 w-4" />
                    )}
                  </DropdownMenuItem>
                ))}
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <IconSettings className="h-4 w-4" />
                  <span>Map Settings</span>
                </DropdownMenuItem>
                <DropdownMenuItem asChild>
                  <a href={AppRoutes.getRoute("InitializePage")}>
                    <IconPlus className="h-4 w-4" />
                    <span>New Map</span>
                  </a>
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </SidebarHeader>

          <SidebarContent>
            {/* Active Layer */}
            <SidebarGroup>
              <SidebarGroupLabel>
                Active Layer
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground ml-auto">
                      <IconInfoCircle className="h-3.5 w-3.5" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="right" className="w-80">
                    <div className="space-y-2">
                      <h4 className="font-semibold">Active Layer</h4>
                      <p className="text-muted-foreground text-sm">
                        Select which geographic layer you want to work with. All
                        editing tools and selection operations will apply to
                        this layer.
                      </p>
                      <div className="text-muted-foreground text-xs">
                        <strong>Tip:</strong> Use keyboard shortcuts 1-4 to
                        quickly switch between layers.
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <Select defaultValue="zip_codes">
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {LAYERS.map((layer) => (
                      <SelectItem key={layer.id} value={layer.id}>
                        {layer.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SidebarGroupContent>
            </SidebarGroup>

            {/* Selection */}
            <SidebarGroup>
              <SidebarGroupLabel>
                Selection
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground ml-auto">
                      <IconInfoCircle className="h-3.5 w-3.5" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="right" className="w-80">
                    <div className="space-y-2">
                      <h4 className="font-semibold">Selection Tools</h4>
                      <p className="text-muted-foreground text-sm">
                        Perform actions on selected map features. Use the lasso
                        tool or click to select features from the active layer.
                      </p>
                      <ul className="text-muted-foreground space-y-1 text-xs">
                        <li>
                          • <strong>Assign:</strong> Add to territory
                        </li>
                        <li>
                          • <strong>Move:</strong> Transfer between territories
                        </li>
                        <li>
                          • <strong>Merge:</strong> Combine features
                        </li>
                        <li>
                          • <strong>Split:</strong> Divide features
                        </li>
                      </ul>
                    </div>
                  </PopoverContent>
                </Popover>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <div className="bg-muted rounded-lg p-3">
                  <div className="mb-3 text-center">
                    <div className="text-foreground text-2xl font-bold">0</div>
                    <div className="text-muted-foreground text-xs">
                      items selected
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <Button variant="outline" size="sm" disabled>
                      <IconPlus className="h-4 w-4" />
                      Assign
                    </Button>
                    <Button variant="outline" size="sm" disabled>
                      Move
                    </Button>
                    <Button variant="outline" size="sm" disabled>
                      Merge
                    </Button>
                    <Button variant="outline" size="sm" disabled>
                      Split
                    </Button>
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled
                      className="col-span-2"
                    >
                      <IconTrash className="h-4 w-4" />
                      Remove
                    </Button>
                  </div>
                </div>
              </SidebarGroupContent>
            </SidebarGroup>

            {/* Base Map */}
            <SidebarGroup>
              <SidebarGroupLabel>
                Base Map
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground ml-auto">
                      <IconInfoCircle className="h-3.5 w-3.5" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="right" className="w-80">
                    <div className="space-y-2">
                      <h4 className="font-semibold">Base Map Style</h4>
                      <p className="text-muted-foreground text-sm">
                        Choose the background map that works best for your
                        workflow. Each style provides different context.
                      </p>
                      <ul className="text-muted-foreground space-y-1 text-xs">
                        <li>
                          • <strong>OpenStreetMap:</strong> Detailed streets and
                          labels
                        </li>
                        <li>
                          • <strong>Satellite:</strong> Aerial imagery
                        </li>
                        <li>
                          • <strong>Terrain:</strong> Topographic features
                        </li>
                        <li>
                          • <strong>Dark:</strong> Reduced eye strain
                        </li>
                      </ul>
                    </div>
                  </PopoverContent>
                </Popover>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <Select
                  value={baseMap}
                  onValueChange={(value) => {
                    setBaseMap(value as typeof baseMap)
                  }}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BASE_MAPS.map((baseMap) => (
                      <SelectItem key={baseMap.id} value={baseMap.id}>
                        {baseMap.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </SidebarGroupContent>
            </SidebarGroup>

            {/* Overlays */}
            {/* <SidebarGroup>
              <SidebarGroupLabel>
                Overlays
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground ml-auto">
                      <IconInfoCircle className="h-3.5 w-3.5" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="right" className="w-80">
                    <div className="space-y-2">
                      <h4 className="font-semibold">Map Overlays</h4>
                      <p className="text-muted-foreground text-sm">
                        Add contextual data layers on top of your base map to
                        help with territory planning and analysis.
                      </p>
                      <div className="text-muted-foreground text-xs">
                        <strong>Note:</strong> Overlays may affect map
                        performance when multiple are enabled.
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <div className="space-y-2">
                  {OVERLAYS.map((overlay) => (
                    <label key={overlay.id} className="flex items-center gap-2">
                      <input type="checkbox" className="rounded border-input" />
                      <span className="text-sm">{overlay.name}</span>
                    </label>
                  ))}
                </div>
              </SidebarGroupContent>
            </SidebarGroup> */}

            {/* Layers */}
            <SidebarGroup>
              <SidebarGroupLabel>
                Layers
                <Popover>
                  <PopoverTrigger asChild>
                    <button className="text-muted-foreground hover:text-foreground ml-auto">
                      <IconInfoCircle className="h-3.5 w-3.5" />
                    </button>
                  </PopoverTrigger>
                  <PopoverContent side="right" className="w-80">
                    <div className="space-y-2">
                      <h4 className="font-semibold">Layer Visibility</h4>
                      <p className="text-muted-foreground text-sm">
                        Control which territory layers are displayed on the map.
                        Hiding layers can improve performance and reduce visual
                        clutter.
                      </p>
                      <div className="text-muted-foreground text-xs">
                        <strong>Tip:</strong> You can still select features from
                        hidden layers if they are set as the active layer.
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </SidebarGroupLabel>
              <SidebarGroupContent>
                <div className="space-y-2">
                  {LAYERS.map((layer) => (
                    <label key={layer.id} className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={visibleLayers[layer.id]}
                        onChange={() => {
                          toggleLayerVisibility(layer.id)
                        }}
                        className="rounded border-input"
                      />
                      <span className="text-sm font-medium">{layer.name}</span>
                    </label>
                  ))}
                </div>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>

          <SidebarFooter className="border-border border-t p-4">
            <Button
              variant="outline"
              className="w-full justify-start"
              onClick={toggleTheme}
            >
              {isDark ? (
                <>
                  <IconSun className="h-4 w-4" />
                  <span>Light Mode</span>
                </>
              ) : (
                <>
                  <IconMoon className="h-4 w-4" />
                  <span>Dark Mode</span>
                </>
              )}
            </Button>
          </SidebarFooter>
        </Sidebar>
      </PageLayout.SideNav>

      <PageLayout.TopNav>
        <div className="flex w-full items-center gap-4">
          <SidebarTrigger />
          <Input type="search" className="max-w-80" />
        </div>
      </PageLayout.TopNav>

      <PageLayout.FullScreenBody>
        <Map
          baseMap={{ type: baseMap }}
          layers={LAYERS.map((layer) => ({
            ...layer,
            visible: visibleLayers[layer.id],
            mvtUrl: `/api/mvt/${layer.id}/{z}/{x}/{y}`,
          }))}
        />
      </PageLayout.FullScreenBody>
    </PageLayout>
  )
}
