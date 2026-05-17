const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function apiFetch<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export function useApi() {
  return {
    getDatasets: () => apiFetch<{ datasets: import("../types").Dataset[] }>("/api/datasets"),

    getDatasetDetails: (name: string) =>
      apiFetch<{ dataset: import("../types").Dataset; sample_data: Record<string, unknown>[] }>(
        `/api/datasets/${name}`
      ),

    getDatasetSample: (name: string, limit = 50) =>
      apiFetch<{ data: Record<string, unknown>[]; columns: import("../types").Column[] }>(
        `/api/datasets/${name}/sample?limit=${limit}`
      ),

    askQuestion: (question: string, dataset?: string, sessionId?: string) =>
      apiFetch<import("../types").AskResponse>("/api/ask", {
        method: "POST",
        body: JSON.stringify({ question, dataset, session_id: sessionId }),
      }),

    runQuery: (sql: string) =>
      apiFetch<{ columns: string[]; rows: Record<string, unknown>[]; row_count: number }>(
        "/api/query",
        {
          method: "POST",
          body: JSON.stringify({ sql }),
        }
      ),

    getHistory: (limit = 50) =>
      apiFetch<{ history: import("../types").QueryHistoryItem[] }>(`/api/history?limit=${limit}`),

    getSuggestedQuestions: () =>
      apiFetch<{ questions: import("../types").SuggestedQuestion[] }>("/api/suggested-questions"),

    getSettings: () =>
      apiFetch<{ has_api_key: boolean; api_key_preview: string | null; model: string }>(
        "/api/settings"
      ),

    updateSettings: (settings: { openai_api_key?: string; openai_model?: string }) =>
      apiFetch<{ status: string }>("/api/settings", {
        method: "POST",
        body: JSON.stringify(settings),
      }),

    getSchema: () =>
      apiFetch<{ schema: string; tables: import("../types").Dataset[] }>("/api/schema"),

    getSemanticLayer: () =>
      apiFetch<import("../types").SemanticLayerSummary>("/api/semantic"),

    getSemanticColumns: (tableName?: string) =>
      apiFetch<{ columns: import("../types").SemanticColumnDescription[] }>(
        `/api/semantic/columns${tableName ? `?table_name=${tableName}` : ""}`
      ),

    getSemanticMetrics: (tableName?: string) =>
      apiFetch<{ metrics: import("../types").SemanticMetric[] }>(
        `/api/semantic/metrics${tableName ? `?table_name=${tableName}` : ""}`
      ),

    getSemanticGlossary: () =>
      apiFetch<{ glossary: import("../types").SemanticGlossaryEntry[] }>("/api/semantic/glossary"),

    getSemanticTrustedQueries: (tableName?: string) =>
      apiFetch<{ trusted_queries: import("../types").SemanticTrustedQuery[] }>(
        `/api/semantic/trusted-queries${tableName ? `?table_name=${tableName}` : ""}`
      ),

    getSessions: () =>
      apiFetch<{
        sessions: {
          id: string;
          created_at: string;
          updated_at: string;
          first_question: string;
          message_count: number;
        }[];
      }>("/api/sessions"),

    getSessionHistory: (sessionId: string) =>
      apiFetch<{
        session_id: string;
        messages: { role: string; content: string; sql: string | null }[];
      }>(`/api/sessions/${sessionId}`),

    // Feedback
    submitFeedback: (data: {
      query_id: string;
      question: string;
      vote: string;
      sql_query?: string;
      session_id?: string;
      comment?: string;
    }) =>
      apiFetch<{ status: string }>("/api/feedback", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    getFeedbackStats: () =>
      apiFetch<import("../types").FeedbackStats>("/api/feedback/stats"),

    // Instructions
    getInstructions: () =>
      apiFetch<{ instructions: import("../types").SemanticInstruction[] }>(
        "/api/semantic/instructions"
      ),

    addInstruction: (data: {
      instruction: string;
      scope?: string;
      dataset_name?: string;
      priority?: number;
    }) =>
      apiFetch<{ status: string }>("/api/semantic/instructions", {
        method: "POST",
        body: JSON.stringify(data),
      }),

    deleteInstruction: (id: number) =>
      apiFetch<{ status: string }>(`/api/semantic/instructions/${id}`, {
        method: "DELETE",
      }),

    // Benchmark
    getBenchmarkCases: (datasetName?: string) =>
      apiFetch<{ cases: import("../types").BenchmarkCase[] }>(
        `/api/benchmark/cases${datasetName ? `?dataset_name=${datasetName}` : ""}`
      ),

    runBenchmark: (datasetName?: string) =>
      apiFetch<import("../types").BenchmarkRunResult>(
        `/api/benchmark/run${datasetName ? `?dataset_name=${datasetName}` : ""}`,
        { method: "POST" }
      ),

    getBenchmarkHistory: () =>
      apiFetch<{ history: import("../types").BenchmarkRunSummary[] }>(
        "/api/benchmark/history"
      ),
  };
}
