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

    askQuestion: (question: string, dataset?: string) =>
      apiFetch<import("../types").AskResponse>("/api/ask", {
        method: "POST",
        body: JSON.stringify({ question, dataset }),
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
  };
}
