export type {
  ColumnSchema,
  DatasetSummary,
  DatasourceSchema,
  DatasourceSummary,
  MetadataPatch,
  MetricDefinition,
  TableSchema,
} from './schema.generated'

export interface HealthResponse {
  status: 'ok'
  app_name: string
  version: string
}
