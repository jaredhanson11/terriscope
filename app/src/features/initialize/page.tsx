import { IconCheck, IconLoader2 } from "@tabler/icons-react"
import { useFormik } from "formik"
import * as React from "react"
import { useNavigate } from "react-router-dom"

import { AppRoutes, PageName } from "@/app/routes"
import Logo from "@/assets/logoipsum.svg?react"
import { PageLayout } from "@/components/layout"
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
} from "@/components/ui/sidebar"
import { cn } from "@/lib/utils"
import { useImportMapMutation } from "@/queries/mutations"
import { queries } from "@/queries/queries"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import DataStep from "./components/data-step"
import ImportStep from "./components/import-step"
import LayerStep from "./components/layer-step"
import ReviewStep from "./components/review-step"
import type {
  DataField,
  DataFields,
  HeadersData,
  LayerFields,
  ValuesData,
} from "./initialize"

interface Step {
  id: string
  title: string
  description: string
  component: React.ReactNode
}

const WIZARD_STEPS_COUNT = 4

export default function InitializePage() {
  const [activeStepIdx, setActiveStepIdx] = React.useState<number>(0)
  const [processingMapId, setProcessingMapId] = React.useState<number | null>(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const importMutation = useImportMapMutation()

  // Poll the map once the import task is queued
  const mapQuery = useQuery({
    ...queries.getMap(processingMapId ?? 0),
    enabled: processingMapId != null,
  })

  // Navigate to home once the job completes
  React.useEffect(() => {
    if (!mapQuery.data) return
    const job = mapQuery.data.active_job
    if (job?.status === "complete" || job == null) {
      void queryClient.invalidateQueries({ queryKey: queries._maps() })
      void navigate(AppRoutes.getRoute(PageName.Home))
    }
  }, [mapQuery.data, navigate, queryClient])

  const isProcessing = processingMapId != null
  const processingStep = mapQuery.data?.active_job?.step ?? "Queuing…"
  const processingFailed = mapQuery.data?.active_job?.status === "failed"

  const formik = useFormik({
    initialValues: {
      name: "",
      headers: [] as HeadersData,
      values: [] as ValuesData,
      layers: [] as LayerFields,
      data_fields: [] as DataFields,
    },
    onSubmit: () => {
      importMutation.mutate(
        {
          import_data: {
            name: formik.values.name,
            headers: formik.values.headers,
            values: formik.values.values,
            layers: formik.values.layers,
            data_fields: formik.values.data_fields.map((f: DataField) => ({
              name: f.name,
              header: f.header,
              type: f.type,
              aggregations: f.aggregations,
            })),
          },
        },
        {
          onSuccess: (data) => {
            setProcessingMapId(data.id)
            setActiveStepIdx(WIZARD_STEPS_COUNT) // advance past wizard steps to processing view
          },
        },
      )
    },
  })

  const STEPS: Step[] = [
    {
      id: "data-source",
      title: "Data Source",
      description: "Upload your data file",
      component: (
        <ImportStep
          onComplete={(headers, values) => {
            void formik.setFieldValue("headers", headers)
            void formik.setFieldValue("values", values)
            setActiveStepIdx(1)
          }}
        />
      ),
    },
    {
      id: "layer-setup",
      title: "Layer Setup",
      description: "Define geographic layers",
      component: (
        <LayerStep
          headers={formik.values.headers}
          onBack={() => {
            setActiveStepIdx(0)
          }}
          onComplete={(layers) => {
            const layerFields: LayerFields = layers
              .filter((l) => l.enabled)
              .map((layer) => ({
                name: layer.name,
                header: layer.idField,
              }))

            void formik.setFieldValue("layers", layerFields)
            setActiveStepIdx(2)
          }}
        />
      ),
    },
    {
      id: "data",
      title: "Data Fields Setup",
      description: "Set up data fields",
      component: (
        <DataStep
          headers={formik.values.headers}
          layerHeaders={formik.values.layers.map((l) => l.header)}
          onBack={() => {
            setActiveStepIdx(1)
          }}
          onComplete={(dataFields) => {
            void formik.setFieldValue("data_fields", dataFields)
            setActiveStepIdx(3)
          }}
        />
      ),
    },
    {
      id: "review",
      title: "Review & Launch",
      description: "Confirm settings and create project",
      component: (
        <ReviewStep
          name={formik.values.name}
          headers={formik.values.headers}
          values={formik.values.values}
          layerFields={formik.values.layers}
          dataFields={formik.values.data_fields}
          onNameChange={(name) => {
            void formik.setFieldValue("name", name)
          }}
          onBack={() => {
            setActiveStepIdx(2)
          }}
          onComplete={() => {
            formik.handleSubmit()
          }}
        />
      ),
    },
  ]

  const activeStep = STEPS[activeStepIdx]

  return (
    <PageLayout>
      <PageLayout.SideNav>
        <Sidebar>
          <SidebarHeader className="p-4 gap-4">
            <Logo className="h-8" />
          </SidebarHeader>
          <SidebarContent>
            <SidebarGroup>
              <SidebarGroupLabel>Progress</SidebarGroupLabel>
              <SidebarGroupContent>
                <div className="space-y-1">
                  {STEPS.map((step, index) => {
                    const isActive = !isProcessing && index === activeStepIdx
                    const isCompleted = isProcessing || index < activeStepIdx
                    const isUpcoming = !isProcessing && index > activeStepIdx
                    return (
                      <div
                        key={step.id}
                        className={cn(
                          "flex items-start gap-3 rounded-lg p-3 transition-colors",
                          isActive && "bg-accent",
                          isCompleted && "text-muted-foreground opacity-60",
                        )}
                      >
                        <div
                          className={cn(
                            "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold",
                            isCompleted && "border-primary bg-primary text-primary-foreground",
                            isActive && "border-primary text-primary",
                            isUpcoming && "border-muted-foreground/30 text-muted-foreground",
                          )}
                        >
                          {isCompleted ? <IconCheck className="h-4 w-4" /> : index + 1}
                        </div>
                        <div className="flex-1 space-y-0.5">
                          <div
                            className={cn(
                              "text-sm font-medium leading-tight",
                              isActive && "text-foreground",
                            )}
                          >
                            {step.title}
                          </div>
                          <div
                            className={cn(
                              "text-xs leading-tight",
                              isActive ? "text-muted-foreground" : "text-muted-foreground/70",
                            )}
                          >
                            {step.description}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                  {/* Processing step — only visible after submit */}
                  <div
                    className={cn(
                      "flex items-start gap-3 rounded-lg p-3 transition-colors",
                      isProcessing && !processingFailed && "bg-accent",
                      processingFailed && "text-destructive",
                    )}
                  >
                    <div
                      className={cn(
                        "mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 text-xs font-semibold",
                        isProcessing && !processingFailed && "border-primary text-primary",
                        !isProcessing && "border-muted-foreground/30 text-muted-foreground",
                        processingFailed && "border-destructive text-destructive",
                      )}
                    >
                      {STEPS.length + 1}
                    </div>
                    <div className="flex-1 space-y-0.5">
                      <div
                        className={cn(
                          "text-sm font-medium leading-tight",
                          isProcessing && "text-foreground",
                          !isProcessing && "text-muted-foreground/70",
                        )}
                      >
                        Processing
                      </div>
                      <div className="text-xs leading-tight text-muted-foreground/70">
                        Computing territories
                      </div>
                    </div>
                  </div>
                </div>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </PageLayout.SideNav>

      <PageLayout.TopNav>
        <div className="flex w-full items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">
              {isProcessing ? "Processing" : activeStep.title}
            </h1>
            <p className="text-muted-foreground text-sm">
              {isProcessing
                ? `Step ${STEPS.length + 1} of ${STEPS.length + 1}`
                : `Step ${activeStepIdx + 1} of ${STEPS.length}`}
            </p>
          </div>
        </div>
      </PageLayout.TopNav>

      <PageLayout.ScrollableBody>
        {isProcessing ? (
          <div className="flex flex-col items-center justify-center gap-6 py-24 text-center">
            {processingFailed ? (
              <>
                <p className="text-destructive text-lg font-medium">Import failed</p>
                <p className="text-muted-foreground text-sm max-w-sm">
                  {mapQuery.data?.active_job?.error ?? "An unexpected error occurred."}
                </p>
              </>
            ) : (
              <>
                <IconLoader2 className="h-10 w-10 animate-spin text-primary" />
                <div className="space-y-1">
                  <p className="text-lg font-medium">Building your map…</p>
                  <p className="text-muted-foreground text-sm">{processingStep}</p>
                </div>
              </>
            )}
          </div>
        ) : (
          activeStep.component
        )}
      </PageLayout.ScrollableBody>
    </PageLayout>
  )
}
