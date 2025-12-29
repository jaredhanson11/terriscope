import createClient from "openapi-fetch"

import config from "@/app/config"
import type { paths } from "@/lib/api/v1"

export const fetchClient = createClient<paths>({
  baseUrl: config.get("api_base_url"),
  credentials: "include",
})
