export type LayerField = {
  name: string
  header: string
}
export type LayerFields = LayerField[]
export type NumberDataFieldOption = "average" | "sum" | "min" | "max"
export type NumberDataField = {
  name: string
  header: string
  type: "number"
  options: Set<NumberDataFieldOption>
}
export type TextDataField = {
  name: string
  header: string
  type: "text"
}
export type DataFields = (NumberDataField | TextDataField)[]
export type HeadersData = string[]
export type ValuesData = (string | number | null)[][]
export type CellData = string | number | null
