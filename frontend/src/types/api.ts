// The health contract is handwritten for the scaffold.
// Generate feature contracts from backend OpenAPI when those endpoints are implemented.
export interface HealthResponse {
  status: 'ok'
  app_name: string
  version: string
}
