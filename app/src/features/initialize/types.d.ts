export type LayerField = {
  name: string
  header: string
  parentHeader: string
}
export type RootLayerField = {
  name: string
  header: string
  parentHeader: undefined
}
export type LayerFields = [RootLayerField, ...LayerField[]]
export type NumberDataField = {
  name: string
  header: string
  type: "number"
  options: Set[NumberDataFieldOption]
}
export type NumberDataFieldOption = "average" | "sum" | "min" | "max"
export type TextDataField = {
  name: string
  header: string
  type: "text"
}
export type DataFields = (NumberDataField | TextDataField)[]
export type HeadersData = string[]
export type ValuesData = (string | number | boolean | Date | null)[][]

export type CellData = string | number | boolean | Date | null
