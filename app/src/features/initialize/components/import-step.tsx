import { IconCloudUpload, IconX } from "@tabler/icons-react"
import * as React from "react"
import * as XLSX from "xlsx"

import XLSXIcon from "@/assets/xlsx-icon.svg?react"
import { Button } from "@/components/ui/button"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
import type { CellData } from "@/features/initialize/types"
import { cn } from "@/lib/utils"

const MAX_FILE_SIZE_MB = 50
const PREVIEW_ROWS = 5

type ImportSelection = {
  file: File
  workbook: XLSX.WorkBook | null
  sheet: [XLSX.WorkSheet, string] | null // sheet and name
}

export default function ImportStep({
  onComplete,
}: {
  onComplete: (headers: string[], data: CellData[][]) => void
}) {
  const [dragActive, setDragActive] = React.useState(false)
  const [selection, setSelection] = React.useState<ImportSelection | null>(null)
  const fileInputRef = React.useRef<HTMLInputElement>(null)

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true)
    } else if (e.type === "dragleave") {
      setDragActive(false)
    }
  }

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)

    if (e.dataTransfer.files.length) {
      void handleFile(e.dataTransfer.files[0])
    }
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.preventDefault()
    if (e.target.files && e.target.files.length) {
      void handleFile(e.target.files[0])
    }
  }

  const handleFile = async (file: File) => {
    const validTypes = [
      "text/csv",
      "application/vnd.ms-excel",
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      ".xlsx",
      ".ztt",
    ]
    const fileExtension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`
    const isValid =
      validTypes.includes(file.type) || validTypes.includes(fileExtension)

    // Validate file size (e.g., max 50MB)
    const maxSize = MAX_FILE_SIZE_MB * 1024 * 1024 // 50MB
    if (file.size > maxSize) {
      return
    }
    if (!isValid) {
      return
    }

    // Read and parse the file with xlsx

    const arrayBuffer = await file.arrayBuffer()
    const workbook = XLSX.read(arrayBuffer, { type: "buffer", sheetRows: 10 })
    let sheet: [XLSX.WorkSheet, string] | null = null

    // Auto-select first sheet if only one exists
    if (workbook.SheetNames.length === 1) {
      sheet = [workbook.Sheets[workbook.SheetNames[0]], workbook.SheetNames[0]]
    }
    setSelection({ file, workbook, sheet })
  }

  const handleRemoveFile = () => {
    setSelection(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const handleSheetSelect = (sheetName: string) => {
    setSelection((prev) => {
      if (prev && prev.workbook) {
        const sheet: [XLSX.WorkSheet, string] = [
          prev.workbook.Sheets[sheetName],
          sheetName,
        ]
        return { ...prev, sheet }
      }
      return prev
    })
  }

  const handleImport = () => {
    if (selection && selection.sheet) {
      selection.file
        .arrayBuffer()
        .then((arrayBuffer) => {
          if (selection.sheet) {
            const workbook = XLSX.read(arrayBuffer, {
              type: "array",
              sheets: [selection.sheet[1]],
            })
            const jsonData: CellData[][] = XLSX.utils.sheet_to_json(
              workbook.Sheets[selection.sheet[1]],
              { header: 1, raw: true, defval: "" },
            )
            onComplete(jsonData[0] as string[], jsonData.slice(1))
          }
        })
        .catch(() => undefined) // TODO: handle random errors with toast
    }
  }

  const handleButtonClick = () => {
    fileInputRef.current?.click()
  }

  return (
    <div className="flex items-center justify-center p-6">
      <div className="w-full max-w-2xl flex flex-col gap-6">
        {!selection && (
          <div
            className={cn(
              "border-border hover:border-primary/50 relative rounded-lg border-2 border-dashed p-12 text-center transition-colors",
              dragActive && "border-primary bg-accent",
            )}
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
          >
            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={handleChange}
              accept=".csv,.ztt,.xlsx"
            />

            <div className="mx-auto flex flex-col items-center">
              <IconCloudUpload className="text-muted-foreground mb-4 h-16 w-16" />
              <h3 className="mb-2 text-lg font-semibold">
                Upload Territory Data
              </h3>
              <p className="text-muted-foreground mb-4 text-sm">
                Drag and drop your file here, or click to browse
              </p>
              <Button onClick={handleButtonClick}>Select File</Button>
              <p className="text-muted-foreground mt-4 text-xs">
                Supported formats: GeoJSON, CSV, Shapefile (ZIP) • Max size:
                50MB
              </p>
            </div>
          </div>
        )}

        {selection && (
          <div className="rounded-lg border border-border bg-card p-8">
            <div className="flex items-start gap-4">
              <XLSXIcon className={"flex h-12 w-12"} />
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold">{selection.file.name}</h4>
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    onClick={handleRemoveFile}
                  >
                    <IconX className="h-4 w-4" />
                  </Button>
                </div>
                <p className="text-muted-foreground text-sm">
                  {(selection.file.size / 1024 / 1024).toFixed(2)} MB
                </p>
              </div>
            </div>
          </div>
        )}
        {selection && selection.workbook && (
          <div className="space-y-3">
            <h3 className="text-sm font-medium text-muted-foreground">
              Select Sheet
            </h3>
            <div className="flex flex-wrap gap-2">
              {selection.workbook.SheetNames.map((sheetName) => {
                const worksheet = selection.workbook?.Sheets[sheetName]
                if (!worksheet) return null
                return (
                  <button
                    key={sheetName}
                    onClick={() => {
                      handleSheetSelect(sheetName)
                    }}
                    className={cn(
                      "rounded-md border px-3 py-1.5 text-sm transition-colors hover:border-primary/50",
                      sheetName === selection.sheet?.[1]
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-background",
                    )}
                  >
                    <span className="font-medium">{sheetName}</span>
                  </button>
                )
              })}
            </div>
          </div>
        )}

        {selection?.sheet && (
          <div className="space-y-4">
            <h3 className="text-lg font-semibold">
              Preview - {selection.sheet[1]}
            </h3>
            <div className="overflow-x-auto rounded-lg border border-border">
              <Table>
                <TableHeader>
                  <TableRow>
                    {(() => {
                      const data = XLSX.utils.sheet_to_json(
                        selection.sheet[0],
                        { header: 1, defval: "" },
                      ) as unknown as unknown[][]
                      return data[0]?.map((cell, i) => (
                        <TableHead key={i}>{String(cell)}</TableHead>
                      ))
                    })()}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(() => {
                    const data = XLSX.utils.sheet_to_json(selection.sheet[0], {
                      header: 1,
                      defval: "",
                    }) as unknown as unknown[][]
                    return data.slice(1, PREVIEW_ROWS + 1).map((row, i) => (
                      <TableRow key={i}>
                        {row.map((cell, j) => (
                          <TableCell key={j}>{String(cell)}</TableCell>
                        ))}
                      </TableRow>
                    ))
                  })()}
                </TableBody>
              </Table>
            </div>
            <div className="flex justify-end">
              <Button onClick={handleImport} size="lg">
                Import Data
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
