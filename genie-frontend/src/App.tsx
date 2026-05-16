import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send,
  Sparkles,
  Settings,
  Database,
  History,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  Globe,
  ShoppingCart,
  Users,
  Package,
  TrendingUp,
  BarChart3,
  Building,
  PieChart,
  Table2,
  BarChart,
} from "lucide-react";
import { useApi } from "./hooks/useApi";
import { ResultsTable } from "./components/ResultsTable";
import { ChartView } from "./components/ChartView";
import { SqlDisplay } from "./components/SqlDisplay";
import { DatasetExplorer } from "./components/DatasetExplorer";
import { QueryHistory } from "./components/QueryHistory";
import { SettingsModal } from "./components/SettingsModal";
import type { ConversationMessage, SuggestedQuestion } from "./types";

const ICON_MAP: Record<string, React.ReactNode> = {
  globe: <Globe className="w-4 h-4" />,
  "shopping-cart": <ShoppingCart className="w-4 h-4" />,
  users: <Users className="w-4 h-4" />,
  package: <Package className="w-4 h-4" />,
  "trending-up": <TrendingUp className="w-4 h-4" />,
  "bar-chart": <BarChart3 className="w-4 h-4" />,
  building: <Building className="w-4 h-4" />,
  "pie-chart": <PieChart className="w-4 h-4" />,
};

type SidebarTab = "datasets" | "history";

function App() {
  const api = useApi();
  const [messages, setMessages] = useState<ConversationMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("datasets");
  const [suggestions, setSuggestions] = useState<SuggestedQuestion[]>([]);
  const [activeView, setActiveView] = useState<"table" | "chart">("table");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.getSuggestedQuestions().then((res) => setSuggestions(res.questions));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSubmit = useCallback(
    async (question?: string) => {
      const q = question || input.trim();
      if (!q || loading) return;
      setInput("");

      const userMsg: ConversationMessage = {
        id: crypto.randomUUID(),
        type: "user",
        content: q,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);

      try {
        const response = await api.askQuestion(q);
        const assistantMsg: ConversationMessage = {
          id: crypto.randomUUID(),
          type: "assistant",
          content: response.explanation || "Here are the results:",
          response,
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, assistantMsg]);
        if (response.chart_config) {
          setActiveView("chart");
        } else {
          setActiveView("table");
        }
      } catch (err) {
        const errorMsg: ConversationMessage = {
          id: crypto.randomUUID(),
          type: "assistant",
          content:
            err instanceof Error
              ? err.message
              : "An error occurred while processing your question.",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMsg]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, api]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const isEmptyState = messages.length === 0;

  return (
    <div className="h-screen flex bg-gray-950">
      {/* Sidebar */}
      <div
        className={`${
          sidebarOpen ? "w-72" : "w-0"
        } transition-all duration-300 border-r border-gray-800 bg-gray-900 flex flex-col overflow-hidden flex-shrink-0`}
      >
        <div className="p-4 border-b border-gray-800 flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="text-sm font-bold text-white">Data Genie</h1>
            <p className="text-xs text-gray-500">AI Data Assistant</p>
          </div>
        </div>

        {/* Sidebar Tabs */}
        <div className="flex border-b border-gray-800">
          <button
            onClick={() => setSidebarTab("datasets")}
            className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              sidebarTab === "datasets"
                ? "text-indigo-400 border-b-2 border-indigo-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <Database className="w-3.5 h-3.5" />
            Datasets
          </button>
          <button
            onClick={() => setSidebarTab("history")}
            className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              sidebarTab === "history"
                ? "text-indigo-400 border-b-2 border-indigo-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <History className="w-3.5 h-3.5" />
            History
          </button>
        </div>

        {/* Sidebar Content */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {sidebarTab === "datasets" ? (
            <DatasetExplorer
              onSelectDataset={(name) => {
                setInput(`Show all data from ${name.replace(/_/g, " ")}`);
                inputRef.current?.focus();
              }}
            />
          ) : (
            <QueryHistory onSelectQuery={(q) => handleSubmit(q)} />
          )}
        </div>

        {/* Settings Button */}
        <div className="p-3 border-t border-gray-800">
          <button
            onClick={() => setSettingsOpen(true)}
            className="w-full flex items-center gap-2 px-3 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
          >
            <Settings className="w-4 h-4" />
            Settings
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-gray-800 bg-gray-900/50">
          <button
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="text-gray-400 hover:text-white transition-colors"
          >
            {sidebarOpen ? (
              <ChevronLeft className="w-5 h-5" />
            ) : (
              <ChevronRight className="w-5 h-5" />
            )}
          </button>
          <div className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-indigo-400" />
            <h1 className="text-base font-semibold text-white">Data Genie</h1>
          </div>
          <span className="text-xs text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
            AI-Powered Data Assistant
          </span>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto scrollbar-thin">
          {isEmptyState ? (
            <div className="flex flex-col items-center justify-center h-full px-4">
              <div className="w-16 h-16 bg-indigo-600/20 rounded-2xl flex items-center justify-center mb-6">
                <Sparkles className="w-8 h-8 text-indigo-400" />
              </div>
              <h2 className="text-2xl font-bold text-white mb-2">
                Ask anything about your data
              </h2>
              <p className="text-gray-400 text-center max-w-lg mb-8">
                Data Genie translates your natural language questions into SQL queries,
                executes them, and visualizes the results. Try a question below or type your own.
              </p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 max-w-2xl w-full">
                {suggestions.map((s, i) => (
                  <button
                    key={i}
                    onClick={() => handleSubmit(s.text)}
                    className="flex items-center gap-3 px-4 py-3 bg-gray-800/50 border border-gray-700 rounded-xl hover:bg-gray-800 hover:border-gray-600 transition-all text-left group"
                  >
                    <div className="w-8 h-8 bg-gray-700 group-hover:bg-indigo-600/30 rounded-lg flex items-center justify-center text-gray-400 group-hover:text-indigo-400 transition-colors flex-shrink-0">
                      {ICON_MAP[s.icon] || <BarChart className="w-4 h-4" />}
                    </div>
                    <span className="text-sm text-gray-300 group-hover:text-white transition-colors">
                      {s.text}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="max-w-4xl mx-auto py-6 px-4 space-y-6">
              {messages.map((msg) => (
                <div key={msg.id}>
                  {msg.type === "user" ? (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 bg-gray-700 rounded-lg flex items-center justify-center flex-shrink-0">
                        <span className="text-sm font-medium text-gray-300">U</span>
                      </div>
                      <div className="flex-1 pt-1">
                        <p className="text-white">{msg.content}</p>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 bg-indigo-600/20 rounded-lg flex items-center justify-center flex-shrink-0">
                        <Sparkles className="w-4 h-4 text-indigo-400" />
                      </div>
                      <div className="flex-1 pt-1 space-y-4 min-w-0">
                        {msg.response?.error && (
                          <div className="flex items-start gap-2 px-3 py-2 bg-red-900/20 border border-red-800/50 rounded-lg text-red-300 text-sm">
                            <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                            {msg.response.error}
                          </div>
                        )}

                        <p className="text-gray-300 text-sm">{msg.content}</p>

                        {msg.response?.sql_query && (
                          <SqlDisplay
                            sql={msg.response.sql_query}
                            explanation={msg.response.explanation}
                          />
                        )}

                        {msg.response && msg.response.rows.length > 0 && (
                          <div className="space-y-3">
                            {msg.response.chart_config && (
                              <div className="flex gap-1 bg-gray-800 rounded-lg p-1 w-fit">
                                <button
                                  onClick={() => setActiveView("table")}
                                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                                    activeView === "table"
                                      ? "bg-gray-700 text-white"
                                      : "text-gray-400 hover:text-white"
                                  }`}
                                >
                                  <Table2 className="w-3.5 h-3.5" />
                                  Table
                                </button>
                                <button
                                  onClick={() => setActiveView("chart")}
                                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                                    activeView === "chart"
                                      ? "bg-gray-700 text-white"
                                      : "text-gray-400 hover:text-white"
                                  }`}
                                >
                                  <BarChart3 className="w-3.5 h-3.5" />
                                  Chart
                                </button>
                              </div>
                            )}

                            {activeView === "table" || !msg.response.chart_config ? (
                              <ResultsTable
                                columns={msg.response.columns}
                                rows={msg.response.rows}
                              />
                            ) : (
                              msg.response.chart_config && (
                                <ChartView
                                  config={msg.response.chart_config}
                                  data={msg.response.rows}
                                />
                              )
                            )}

                            <p className="text-xs text-gray-500">
                              {msg.response.row_count} row{msg.response.row_count !== 1 ? "s" : ""} returned
                            </p>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              ))}

              {loading && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 bg-indigo-600/20 rounded-lg flex items-center justify-center flex-shrink-0">
                    <Sparkles className="w-4 h-4 text-indigo-400" />
                  </div>
                  <div className="flex items-center gap-2 pt-2">
                    <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                    <span className="text-sm text-gray-400">Analyzing your question...</span>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area */}
        <div className="border-t border-gray-800 bg-gray-900/50 p-4">
          <div className="max-w-4xl mx-auto">
            <div className="flex items-end gap-3 bg-gray-800 border border-gray-700 rounded-xl px-4 py-3 focus-within:border-indigo-500 focus-within:ring-1 focus-within:ring-indigo-500 transition-all">
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your data... (e.g., 'What are the top 10 countries by GDP?')"
                className="flex-1 bg-transparent text-white placeholder-gray-500 resize-none outline-none text-sm min-h-6 max-h-32"
                rows={1}
                disabled={loading}
              />
              <button
                onClick={() => handleSubmit()}
                disabled={!input.trim() || loading}
                className="flex-shrink-0 w-8 h-8 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg flex items-center justify-center transition-colors"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </button>
            </div>
            <p className="text-xs text-gray-600 mt-2 text-center">
              Data Genie converts your questions to SQL and executes them against the loaded datasets.
              Configure your OpenAI API key in Settings for best results.
            </p>
          </div>
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}

export default App
