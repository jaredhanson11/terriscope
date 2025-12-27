export type Step = {
  id: string
  title: string
  description: string
  status: "completed" | "current" | "upcoming"
}
