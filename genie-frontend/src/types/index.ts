export interface Column {
  name: string;
  type: string;
  nullable: boolean;
}

export interface Dataset {
  name: string;
  columns: Column[];
  row_count: number;
}

export interface ChartConfig {
  chart_type: "bar" | "line" | "pie" | "area" | "scatter" | "none";
  x_axis: string;
  y_axis: string[];
  chart_title: string;
}

export interface PipelineStageInfo {
  name: string;
  status: string;
  duration_ms: number;
  output: Record<string, unknown>;
}

export interface AskResponse {
  question: string;
  sql_query: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  chart_config: ChartConfig | null;
  explanation: string;
  error: string | null;
  pipeline_stages: PipelineStageInfo[];
  total_duration_ms: number;
  result_summary: string;
  follow_ups: string[];
  session_id: string | null;
  is_trusted: boolean;
  needs_clarification: boolean;
  clarification: string | null;
  intent: Record<string, unknown>;
  query_id: string;
}

export interface SuggestedQuestion {
  text: string;
  dataset: string;
  icon: string;
}

export interface QueryHistoryItem {
  id: number;
  question: string;
  sql_query: string;
  result_summary: string | null;
  chart_config: string | null;
  dataset_name: string | null;
  created_at: string;
}

export interface ConversationMessage {
  id: string;
  type: "user" | "assistant";
  content: string;
  response?: AskResponse;
  timestamp: Date;
}

// Semantic Layer types
export interface SemanticColumnDescription {
  id: number;
  table_name: string;
  column_name: string;
  description: string;
  business_name: string | null;
  data_format: string | null;
}

export interface SemanticGlossaryEntry {
  id: number;
  term: string;
  definition: string;
  mapped_table: string | null;
  mapped_column: string | null;
  synonyms: string | null;
}

export interface SemanticMetric {
  id: number;
  name: string;
  description: string;
  table_name: string;
  expression: string;
  format_type: string;
}

export interface SemanticDimension {
  id: number;
  name: string;
  table_name: string;
  column_name: string;
  description: string | null;
}

export interface SemanticFilter {
  id: number;
  name: string;
  table_name: string;
  expression: string;
  description: string | null;
}

export interface SemanticJoin {
  id: number;
  left_table: string;
  right_table: string;
  join_type: string;
  on_clause: string;
  description: string | null;
}

export interface SemanticTrustedQuery {
  id: number;
  question: string;
  sql_query: string;
  description: string | null;
  table_name: string | null;
  is_parameterized: number;
}

export interface SemanticInstruction {
  id: number;
  instruction: string;
  scope: string;
  dataset_name: string | null;
  priority: number;
  is_active: number;
  created_at: string;
}

export interface FeedbackStats {
  total: number;
  upvotes: number;
  downvotes: number;
  accuracy_pct: number;
  recent: FeedbackItem[];
}

export interface FeedbackItem {
  id: number;
  query_id: string;
  session_id: string | null;
  question: string;
  sql_query: string | null;
  vote: string;
  comment: string | null;
  created_at: string;
}

export interface BenchmarkCase {
  id: number;
  question: string;
  expected_sql: string;
  expected_result_pattern: string | null;
  dataset_name: string | null;
  tags: string | null;
  difficulty: string;
  created_at: string;
}

export interface BenchmarkRunSummary {
  id: number;
  run_at: string;
  total_cases: number;
  passed: number;
  failed: number;
  accuracy_pct: number;
  duration_ms: number;
}

export interface BenchmarkRunResult {
  total: number;
  passed: number;
  failed: number;
  accuracy_pct: number;
  duration_ms: number;
  details: BenchmarkCaseResult[];
}

export interface BenchmarkCaseResult {
  question: string;
  dataset: string | null;
  difficulty: string | null;
  tags: string | null;
  passed: boolean;
  checks: { check: string; passed: boolean; detail: string }[];
  generated_sql?: string;
  expected_row_count?: number;
  pipeline_row_count?: number;
  is_trusted?: boolean;
}

export interface SemanticLayerSummary {
  column_descriptions: SemanticColumnDescription[];
  glossary: SemanticGlossaryEntry[];
  metrics: SemanticMetric[];
  dimensions: SemanticDimension[];
  filters: SemanticFilter[];
  joins: SemanticJoin[];
  trusted_queries: SemanticTrustedQuery[];
  instructions: SemanticInstruction[];
}
