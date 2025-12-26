/* Config keys */
// Make sure any keys changed here are adjusted in the setup_config.sh script
export const API_BASE_URL = "api_base_url"

type ConfigKey = typeof API_BASE_URL

class Config {
  appConfig: { [key: string]: string | undefined }

  defaultConfig: { [key: string]: string } = {}

  constructor() {
    this.appConfig = {}
    if (import.meta.env.DEV) {
      // When in development mode, comes from VITE_ENV_VAR
      Object.keys(import.meta.env).forEach((envVar) => {
        if (envVar.toLowerCase().startsWith("vite_")) {
          const key = envVar.toLowerCase().replace("vite_", "")
          const val: string = new String(import.meta.env[envVar]).toString()
          this.appConfig[key] = val
        }
      })
    } else {
      // When in production, comes from config.js file at runtime
      const windowConfig = (
        window as unknown as {
          appConfig: { [key: string]: string } | undefined
        }
      ).appConfig
      if (windowConfig) {
        this.appConfig = {
          ...windowConfig,
        }
      }
    }
  }

  get(configKey: ConfigKey): string {
    let val = this.appConfig[configKey]
    if (val === undefined) {
      val = this.defaultConfig[configKey]
    }
    return val
  }

  set(configKey: ConfigKey, configVal: string | undefined): void {
    /* Updates global app config object */
    this.appConfig[configKey] = configVal
  }
}

const config = new Config()
export default config
