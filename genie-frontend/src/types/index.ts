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

export interface AskResponse {
  question: string;
  sql_query: string;
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  chart_config: ChartConfig | null;
  explanation: string;
  error: string | null;
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

export interface SemanticLayerSummary {
  column_descriptions: SemanticColumnDescription[];
  glossary: SemanticGlossaryEntry[];
  metrics: SemanticMetric[];
  dimensions: SemanticDimension[];
  filters: SemanticFilter[];
  joins: SemanticJoin[];
  trusted_queries: SemanticTrustedQuery[];
}
