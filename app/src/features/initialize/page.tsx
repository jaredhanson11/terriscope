import { IconCheck } from "@tabler/icons-react"
import { useFormik } from "formik"
import * as React from "react"

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

import DataStep from "./components/data-step"
import ImportStep from "./components/import-step"
import LayerStep from "./components/layer-step"
import ReviewStep from "./components/review-step"
import type {
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

export default function InitializePage() {
  const [activeStepIdx, setActiveStepIdx] = React.useState<number>(0)
  const importMutation = useImportMapMutation()
  const formik = useFormik({
    initialValues: {
      name: "",
      headers: [] as HeadersData,
      values: [] as ValuesData,
      layers: [] as LayerFields,
      data_fields: [] as DataFields,
    },
    onSubmit: () => {
      importMutation.mutate({
        import_data: formik.values,
      })
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
                    const isActive = index === activeStepIdx
                    const isCompleted = index < activeStepIdx
                    const isUpcoming = index > activeStepIdx
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
                            isCompleted &&
                              "border-primary bg-primary text-primary-foreground",
                            isActive && "border-primary text-primary",
                            isUpcoming &&
                              "border-muted-foreground/30 text-muted-foreground",
                          )}
                        >
                          {isCompleted ? (
                            <IconCheck className="h-4 w-4" />
                          ) : (
                            index + 1
                          )}
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
                              isActive
                                ? "text-muted-foreground"
                                : "text-muted-foreground/70",
                            )}
                          >
                            {step.description}
                          </div>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </SidebarGroupContent>
            </SidebarGroup>
          </SidebarContent>
        </Sidebar>
      </PageLayout.SideNav>

      <PageLayout.TopNav>
        <div className="flex w-full items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold">{activeStep.title}</h1>
            <p className="text-muted-foreground text-sm">
              Step {activeStepIdx + 1} of {STEPS.length}
            </p>
          </div>
        </div>
      </PageLayout.TopNav>

      <PageLayout.ScrollableBody>
        {activeStep.component}
      </PageLayout.ScrollableBody>
    </PageLayout>
  )
}
