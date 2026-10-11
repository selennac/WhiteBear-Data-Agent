export type {
  AnalysisRun,
  ConversationDetail,
  ConversationSummary,
  ColumnSchema,
  DatasetSummary,
  DatasourceSchema,
  DatasourceSummary,
  MetadataPatch,
  MetricDefinition,
  QueryResult,
  TableSchema,
} from './schema.generated'

export interface HealthResponse {
  status: 'ok'
  app_name: string
  version: string
}
