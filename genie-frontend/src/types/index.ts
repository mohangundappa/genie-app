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
