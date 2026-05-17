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
  MessageSquarePlus,
  Clock,
  Zap,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronUp,
  Shield,
  HelpCircle,
  MessageCircle,
  ThumbsUp,
  ThumbsDown,
  FlaskConical,
  BookOpen,
  Play,
  Plus,
  Trash2,
} from "lucide-react";
import { useApi } from "./hooks/useApi";
import { ResultsTable } from "./components/ResultsTable";
import { ChartView } from "./components/ChartView";
import { SqlDisplay } from "./components/SqlDisplay";
import { DatasetExplorer } from "./components/DatasetExplorer";
import { QueryHistory } from "./components/QueryHistory";
import { SettingsModal } from "./components/SettingsModal";
import { SemanticLayer } from "./components/SemanticLayer";
import type {
  ConversationMessage,
  SuggestedQuestion,
  PipelineStageInfo,
  FeedbackStats,
  SemanticInstruction,
  BenchmarkCase,
  BenchmarkRunResult,
  BenchmarkRunSummary,
} from "./types";

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

type SidebarTab = "datasets" | "history" | "semantic" | "quality";

function SchemaRetrieverDetails({ output }: { output: Record<string, unknown> }) {
  const tableScores = output.table_scores as Record<string, number> | undefined;
  const signalsUsed = output.signals_used as Record<string, number> | undefined;
  const method = output.method as string | undefined;
  const valueMatches = output.value_matches as number | undefined;
  const filterHints = output.filter_hints as string[] | undefined;

  return (
    <div className="mt-1.5 ml-5 space-y-1.5 text-xs">
      {method && (
        <div className="text-indigo-400 italic">{method}</div>
      )}
      {tableScores && Object.keys(tableScores).length > 0 && (
        <div>
          <span className="text-gray-500">Tables: </span>
          {Object.entries(tableScores).map(([table, score], i) => (
            <span key={table}>
              {i > 0 && <span className="text-gray-600">, </span>}
              <span className="text-cyan-400">{table}</span>
              <span className="text-gray-600"> ({(score as number).toFixed(3)})</span>
            </span>
          ))}
        </div>
      )}
      {signalsUsed && Object.keys(signalsUsed).length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(signalsUsed).map(([signal, count]) => (
            <span
              key={signal}
              className="px-1.5 py-0.5 bg-gray-800 border border-gray-700 rounded text-gray-300"
            >
              {signal}: {count as number}
            </span>
          ))}
        </div>
      )}
      {(valueMatches !== undefined && valueMatches > 0) && (
        <div className="text-amber-400">
          {valueMatches} value match{valueMatches !== 1 ? "es" : ""} found in data
        </div>
      )}
      {filterHints && filterHints.length > 0 && (
        <div>
          <span className="text-gray-500">Filter hints: </span>
          {filterHints.map((h, i) => (
            <span key={i} className="text-green-400">{i > 0 ? ", " : ""}{h}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function PipelineStages({ stages, totalMs }: { stages: PipelineStageInfo[]; totalMs: number }) {
  const [expanded, setExpanded] = useState(false);
  const [expandedStage, setExpandedStage] = useState<number | null>(null);
  if (!stages.length) return null;

  return (
    <div className="mt-2">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        <Zap className="w-3 h-3" />
        {stages.length} pipeline stages
        <span className="text-gray-600">({totalMs.toFixed(0)}ms)</span>
        {expanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {expanded && (
        <div className="mt-2 space-y-1 pl-1 border-l-2 border-gray-800">
          {stages.map((s, i) => (
            <div key={i}>
              <button
                onClick={() => setExpandedStage(expandedStage === i ? null : i)}
                className="flex items-center gap-2 pl-3 py-0.5 text-xs w-full text-left hover:bg-gray-800/50 rounded transition-colors"
              >
                {s.status === "completed" ? (
                  <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />
                ) : s.status === "error" ? (
                  <XCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
                ) : (
                  <Clock className="w-3 h-3 text-gray-500 flex-shrink-0" />
                )}
                <span className="text-gray-400 font-mono">{s.name}</span>
                <span className="text-gray-600">{s.duration_ms.toFixed(1)}ms</span>
                {s.name === "schema_retriever" && s.output && (
                  <span className="text-indigo-400 ml-1">
                    {expandedStage === i ? <ChevronUp className="w-3 h-3 inline" /> : <ChevronDown className="w-3 h-3 inline" />}
                  </span>
                )}
              </button>
              {expandedStage === i && s.name === "schema_retriever" && s.output && (
                <SchemaRetrieverDetails output={s.output} />
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FeedbackButtons({
  queryId,
  question,
  sqlQuery,
  sessionId,
}: {
  queryId: string;
  question: string;
  sqlQuery: string;
  sessionId?: string;
}) {
  const api = useApi();
  const [voted, setVoted] = useState<"up" | "down" | null>(null);
  const [showComment, setShowComment] = useState(false);
  const [comment, setComment] = useState("");

  const vote = async (v: "up" | "down") => {
    if (voted) return;
    setVoted(v);
    try {
      await api.submitFeedback({
        query_id: queryId,
        question,
        vote: v,
        sql_query: sqlQuery,
        session_id: sessionId,
        comment: comment || undefined,
      });
    } catch {
      setVoted(null);
    }
    if (v === "down") setShowComment(true);
  };

  return (
    <div className="flex items-center gap-2 mt-1">
      <button
        onClick={() => vote("up")}
        disabled={voted !== null}
        className={`p-1 rounded transition-colors ${
          voted === "up"
            ? "text-green-400 bg-green-900/30"
            : voted
            ? "text-gray-700 cursor-not-allowed"
            : "text-gray-500 hover:text-green-400 hover:bg-green-900/20"
        }`}
        title="Good response"
      >
        <ThumbsUp className="w-3.5 h-3.5" />
      </button>
      <button
        onClick={() => vote("down")}
        disabled={voted !== null}
        className={`p-1 rounded transition-colors ${
          voted === "down"
            ? "text-red-400 bg-red-900/30"
            : voted
            ? "text-gray-700 cursor-not-allowed"
            : "text-gray-500 hover:text-red-400 hover:bg-red-900/20"
        }`}
        title="Bad response"
      >
        <ThumbsDown className="w-3.5 h-3.5" />
      </button>
      {voted && (
        <span className="text-xs text-gray-600">
          {voted === "up" ? "Thanks!" : "Thanks for the feedback"}
        </span>
      )}
      {showComment && !comment && (
        <input
          type="text"
          placeholder="What was wrong?"
          className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 outline-none focus:border-indigo-500 w-48"
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const val = (e.target as HTMLInputElement).value;
              setComment(val);
              setShowComment(false);
              api.submitFeedback({
                query_id: queryId,
                question,
                vote: "down",
                sql_query: sqlQuery,
                session_id: sessionId,
                comment: val,
              });
            }
          }}
        />
      )}
    </div>
  );
}

function QualityPanel() {
  const api = useApi();
  const [tab, setTab] = useState<"feedback" | "benchmark" | "instructions">("feedback");
  const [feedbackStats, setFeedbackStats] = useState<FeedbackStats | null>(null);
  const [instructions, setInstructions] = useState<SemanticInstruction[]>([]);
  const [benchmarkCases, setBenchmarkCases] = useState<BenchmarkCase[]>([]);
  const [benchmarkHistory, setBenchmarkHistory] = useState<BenchmarkRunSummary[]>([]);
  const [benchmarkResult, setBenchmarkResult] = useState<BenchmarkRunResult | null>(null);
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [newInstruction, setNewInstruction] = useState("");
  const [newInstructionScope, setNewInstructionScope] = useState("global");
  const [newInstructionDataset, setNewInstructionDataset] = useState("");

  useEffect(() => {
    if (tab === "feedback") {
      api.getFeedbackStats().then(setFeedbackStats).catch(() => {});
    } else if (tab === "benchmark") {
      api.getBenchmarkCases().then((r) => setBenchmarkCases(r.cases)).catch(() => {});
      api.getBenchmarkHistory().then((r) => setBenchmarkHistory(r.history)).catch(() => {});
    } else if (tab === "instructions") {
      api.getInstructions().then((r) => setInstructions(r.instructions)).catch(() => {});
    }
  }, [tab]);

  const runBenchmark = async () => {
    setRunningBenchmark(true);
    setBenchmarkResult(null);
    try {
      const result = await api.runBenchmark();
      setBenchmarkResult(result);
      api.getBenchmarkHistory().then((r) => setBenchmarkHistory(r.history)).catch(() => {});
    } catch {
      // ignore
    } finally {
      setRunningBenchmark(false);
    }
  };

  const addInstruction = async () => {
    if (!newInstruction.trim()) return;
    await api.addInstruction({
      instruction: newInstruction,
      scope: newInstructionScope,
      dataset_name: newInstructionScope === "dataset" ? newInstructionDataset : undefined,
    });
    setNewInstruction("");
    const r = await api.getInstructions();
    setInstructions(r.instructions);
  };

  const removeInstruction = async (id: number) => {
    await api.deleteInstruction(id);
    const r = await api.getInstructions();
    setInstructions(r.instructions);
  };

  return (
    <div className="p-3 space-y-3">
      {/* Sub-tabs */}
      <div className="flex gap-1 bg-gray-800 rounded-lg p-0.5">
        {(["feedback", "benchmark", "instructions"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`flex-1 py-1.5 text-xs font-medium rounded-md transition-colors capitalize ${
              tab === t ? "bg-gray-700 text-white" : "text-gray-500 hover:text-gray-300"
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Feedback Tab */}
      {tab === "feedback" && feedbackStats && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-lg font-bold text-white">{feedbackStats.accuracy_pct}%</div>
              <div className="text-xs text-gray-500">Accuracy</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-lg font-bold text-green-400">{feedbackStats.upvotes}</div>
              <div className="text-xs text-gray-500">Upvotes</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-2.5 text-center">
              <div className="text-lg font-bold text-red-400">{feedbackStats.downvotes}</div>
              <div className="text-xs text-gray-500">Downvotes</div>
            </div>
          </div>
          {feedbackStats.recent && feedbackStats.recent.length > 0 && (
            <div className="space-y-1.5">
              <h4 className="text-xs text-gray-500 font-medium">Recent Feedback</h4>
              {feedbackStats.recent.slice(0, 10).map((f) => (
                <div
                  key={f.id}
                  className="flex items-start gap-2 text-xs bg-gray-800/50 rounded p-2"
                >
                  {f.vote === "up" ? (
                    <ThumbsUp className="w-3 h-3 text-green-400 mt-0.5 flex-shrink-0" />
                  ) : (
                    <ThumbsDown className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                  )}
                  <div className="min-w-0">
                    <p className="text-gray-300 truncate">{f.question}</p>
                    {f.comment && <p className="text-gray-500 mt-0.5">{f.comment}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Benchmark Tab */}
      {tab === "benchmark" && (
        <div className="space-y-3">
          <button
            onClick={runBenchmark}
            disabled={runningBenchmark}
            className="w-full flex items-center justify-center gap-2 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white text-xs font-medium rounded-lg transition-colors"
          >
            {runningBenchmark ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                Running {benchmarkCases.length} cases...
              </>
            ) : (
              <>
                <Play className="w-3.5 h-3.5" />
                Run Benchmark ({benchmarkCases.length} cases)
              </>
            )}
          </button>

          {benchmarkResult && (
            <div className="space-y-2">
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className={`text-lg font-bold ${benchmarkResult.accuracy_pct >= 70 ? "text-green-400" : benchmarkResult.accuracy_pct >= 40 ? "text-amber-400" : "text-red-400"}`}>
                    {benchmarkResult.accuracy_pct}%
                  </div>
                  <div className="text-xs text-gray-500">Accuracy</div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-green-400">{benchmarkResult.passed}</div>
                  <div className="text-xs text-gray-500">Passed</div>
                </div>
                <div className="bg-gray-800 rounded-lg p-2.5 text-center">
                  <div className="text-lg font-bold text-red-400">{benchmarkResult.failed}</div>
                  <div className="text-xs text-gray-500">Failed</div>
                </div>
              </div>
              <div className="space-y-1">
                {benchmarkResult.details.map((d, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-2 text-xs bg-gray-800/50 rounded p-2"
                  >
                    {d.passed ? (
                      <CheckCircle2 className="w-3 h-3 text-green-400 mt-0.5 flex-shrink-0" />
                    ) : (
                      <XCircle className="w-3 h-3 text-red-400 mt-0.5 flex-shrink-0" />
                    )}
                    <div className="min-w-0">
                      <p className="text-gray-300 truncate">{d.question}</p>
                      <div className="flex gap-1.5 mt-0.5">
                        {d.dataset && (
                          <span className="text-gray-600">{d.dataset}</span>
                        )}
                        {d.difficulty && (
                          <span className={`px-1 rounded ${
                            d.difficulty === "easy" ? "text-green-500" :
                            d.difficulty === "medium" ? "text-amber-500" : "text-red-500"
                          }`}>
                            {d.difficulty}
                          </span>
                        )}
                        {d.is_trusted && (
                          <span className="text-emerald-500">trusted</span>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {benchmarkHistory.length > 0 && !benchmarkResult && (
            <div className="space-y-1.5">
              <h4 className="text-xs text-gray-500 font-medium">Run History</h4>
              {benchmarkHistory.map((h) => (
                <div
                  key={h.id}
                  className="flex items-center justify-between text-xs bg-gray-800/50 rounded p-2"
                >
                  <span className="text-gray-400">
                    {new Date(h.run_at).toLocaleString()}
                  </span>
                  <span className={`font-medium ${h.accuracy_pct >= 70 ? "text-green-400" : "text-amber-400"}`}>
                    {h.accuracy_pct}% ({h.passed}/{h.total_cases})
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Instructions Tab */}
      {tab === "instructions" && (
        <div className="space-y-3">
          <div className="space-y-2">
            <textarea
              value={newInstruction}
              onChange={(e) => setNewInstruction(e.target.value)}
              placeholder="Add an instruction, e.g., 'When asked about revenue, use total_amount not unit_price * quantity'"
              className="w-full text-xs bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-300 outline-none focus:border-indigo-500 resize-none"
              rows={2}
            />
            <div className="flex gap-2">
              <select
                value={newInstructionScope}
                onChange={(e) => setNewInstructionScope(e.target.value)}
                className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 outline-none"
              >
                <option value="global">Global</option>
                <option value="dataset">Dataset</option>
              </select>
              {newInstructionScope === "dataset" && (
                <select
                  value={newInstructionDataset}
                  onChange={(e) => setNewInstructionDataset(e.target.value)}
                  className="text-xs bg-gray-800 border border-gray-700 rounded px-2 py-1 text-gray-300 outline-none"
                >
                  <option value="">Select dataset</option>
                  <option value="sales_orders">sales_orders</option>
                  <option value="employees">employees</option>
                  <option value="world_countries">world_countries</option>
                  <option value="product_inventory">product_inventory</option>
                </select>
              )}
              <button
                onClick={addInstruction}
                disabled={!newInstruction.trim()}
                className="flex items-center gap-1 px-3 py-1 bg-indigo-600 hover:bg-indigo-500 disabled:bg-gray-700 text-white text-xs rounded transition-colors ml-auto"
              >
                <Plus className="w-3 h-3" />
                Add
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            {instructions.map((inst) => (
              <div
                key={inst.id}
                className="flex items-start gap-2 text-xs bg-gray-800/50 rounded p-2 group"
              >
                <BookOpen className="w-3 h-3 text-indigo-400 mt-0.5 flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-gray-300">{inst.instruction}</p>
                  <div className="flex gap-1.5 mt-0.5 text-gray-600">
                    <span>{inst.scope}</span>
                    {inst.dataset_name && <span>/ {inst.dataset_name}</span>}
                    <span>priority: {inst.priority}</span>
                  </div>
                </div>
                <button
                  onClick={() => removeInstruction(inst.id)}
                  className="text-gray-600 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all flex-shrink-0"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

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
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [pipelineLoading, setPipelineLoading] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    api.getSuggestedQuestions().then((res) => setSuggestions(res.questions));
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startNewSession = useCallback(() => {
    setSessionId(crypto.randomUUID());
    setMessages([]);
  }, []);

  const handleSubmit = useCallback(
    async (question?: string) => {
      const q = question || input.trim();
      if (!q || loading) return;
      setInput("");

      // Auto-create session on first message
      const currentSessionId = sessionId || crypto.randomUUID();
      if (!sessionId) setSessionId(currentSessionId);

      const userMsg: ConversationMessage = {
        id: crypto.randomUUID(),
        type: "user",
        content: q,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setLoading(true);
      setPipelineLoading("Classifying intent...");

      try {
        const response = await api.askQuestion(q, undefined, currentSessionId);
        const assistantMsg: ConversationMessage = {
          id: crypto.randomUUID(),
          type: "assistant",
          content: response.result_summary || response.explanation || "Here are the results:",
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
        setPipelineLoading("");
      }
    },
    [input, loading, api, sessionId]
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
          <button
            onClick={() => setSidebarTab("semantic")}
            className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              sidebarTab === "semantic"
                ? "text-indigo-400 border-b-2 border-indigo-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            Semantic
          </button>
          <button
            onClick={() => setSidebarTab("quality")}
            className={`flex-1 py-2.5 text-xs font-medium flex items-center justify-center gap-1.5 transition-colors ${
              sidebarTab === "quality"
                ? "text-indigo-400 border-b-2 border-indigo-400"
                : "text-gray-500 hover:text-gray-300"
            }`}
          >
            <FlaskConical className="w-3.5 h-3.5" />
            Quality
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
          ) : sidebarTab === "history" ? (
            <QueryHistory onSelectQuery={(q) => handleSubmit(q)} />
          ) : sidebarTab === "quality" ? (
            <QualityPanel />
          ) : (
            <SemanticLayer onAskQuestion={(q) => handleSubmit(q)} />
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
            Compound AI Pipeline
          </span>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={startNewSession}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-gray-400 hover:text-white bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" />
              New Chat
            </button>
          </div>
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

                        {/* Clarification request */}
                        {msg.response?.needs_clarification && msg.response.clarification && (
                          <div className="flex items-start gap-2 px-3 py-2.5 bg-amber-900/20 border border-amber-800/50 rounded-lg text-amber-200 text-sm">
                            <HelpCircle className="w-4 h-4 mt-0.5 flex-shrink-0 text-amber-400" />
                            <div>
                              <p className="font-medium text-amber-300 text-xs mb-1">Clarification needed</p>
                              <p>{msg.response.clarification}</p>
                            </div>
                          </div>
                        )}

                        {/* Result summary */}
                        {msg.response?.result_summary && !msg.response?.needs_clarification && (
                          <p className="text-gray-300 text-sm">{msg.response.result_summary}</p>
                        )}
                        {!msg.response?.result_summary && (
                          <p className="text-gray-300 text-sm">{msg.content}</p>
                        )}

                        {/* Trusted badge */}
                        {msg.response?.is_trusted && (
                          <div className="flex items-center gap-1.5 text-xs text-emerald-400">
                            <Shield className="w-3 h-3" />
                            Trusted Query
                          </div>
                        )}

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

                        {/* Pipeline stages */}
                        {msg.response?.pipeline_stages && (
                          <PipelineStages
                            stages={msg.response.pipeline_stages}
                            totalMs={msg.response.total_duration_ms}
                          />
                        )}

                        {/* Feedback buttons */}
                        {msg.response?.sql_query && msg.response?.query_id && (
                          <FeedbackButtons
                            queryId={msg.response.query_id}
                            question={msg.response.question}
                            sqlQuery={msg.response.sql_query}
                            sessionId={sessionId || undefined}
                          />
                        )}

                        {/* Follow-up suggestions */}
                        {msg.response?.follow_ups && msg.response.follow_ups.length > 0 && (
                          <div className="mt-3 space-y-2">
                            <p className="text-xs text-gray-500 flex items-center gap-1">
                              <MessageCircle className="w-3 h-3" />
                              Follow-up questions
                            </p>
                            <div className="flex flex-wrap gap-2">
                              {msg.response.follow_ups.map((fu, i) => (
                                <button
                                  key={i}
                                  onClick={() => handleSubmit(fu)}
                                  className="text-xs px-3 py-1.5 bg-gray-800 border border-gray-700 rounded-full text-gray-300 hover:text-white hover:border-indigo-500 hover:bg-indigo-500/10 transition-all"
                                >
                                  {fu}
                                </button>
                              ))}
                            </div>
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
                    <span className="text-sm text-gray-400">
                      {pipelineLoading || "Processing through compound AI pipeline..."}
                    </span>
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
