import { useState, useEffect } from "react";
import {
  BookOpen,
  Columns,
  Calculator,
  Filter,
  Link2,
  FileCode,
  ChevronDown,
  ChevronRight,
  Search,
  Layers,
} from "lucide-react";
import { useApi } from "../hooks/useApi";
import type {
  SemanticLayerSummary,
  SemanticColumnDescription,
  SemanticGlossaryEntry,
  SemanticMetric,
  SemanticDimension,
  SemanticFilter,
  SemanticJoin,
  SemanticTrustedQuery,
} from "../types";

type SemanticTab =
  | "columns"
  | "glossary"
  | "metrics"
  | "filters"
  | "joins"
  | "trusted";

interface Props {
  onAskQuestion?: (question: string) => void;
}

export function SemanticLayer({ onAskQuestion }: Props) {
  const api = useApi();
  const [data, setData] = useState<SemanticLayerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<SemanticTab>("columns");
  const [search, setSearch] = useState("");
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());

  useEffect(() => {
    api
      .getSemanticLayer()
      .then((res) => {
        setData(res);
        const tables = new Set(res.column_descriptions.map((c) => c.table_name));
        setExpandedTables(tables);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const toggleTable = (table: string) => {
    setExpandedTables((prev) => {
      const next = new Set(prev);
      if (next.has(table)) next.delete(table);
      else next.add(table);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="p-4 text-sm text-gray-500 flex items-center gap-2">
        <Layers className="w-4 h-4 animate-pulse" />
        Loading semantic layer...
      </div>
    );
  }

  if (!data) {
    return (
      <div className="p-4 text-sm text-gray-500">
        Failed to load semantic layer.
      </div>
    );
  }

  const tabs: { key: SemanticTab; label: string; icon: React.ReactNode; count: number }[] = [
    { key: "columns", label: "Columns", icon: <Columns className="w-3 h-3" />, count: data.column_descriptions.length },
    { key: "glossary", label: "Glossary", icon: <BookOpen className="w-3 h-3" />, count: data.glossary.length },
    { key: "metrics", label: "Metrics", icon: <Calculator className="w-3 h-3" />, count: data.metrics.length },
    { key: "filters", label: "Filters", icon: <Filter className="w-3 h-3" />, count: data.filters.length },
    { key: "joins", label: "Joins", icon: <Link2 className="w-3 h-3" />, count: data.joins.length },
    { key: "trusted", label: "Queries", icon: <FileCode className="w-3 h-3" />, count: data.trusted_queries.length },
  ];

  const filterText = search.toLowerCase();

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="px-3 pt-3 pb-2">
        <div className="flex items-center gap-2 bg-gray-800 border border-gray-700 rounded-lg px-2.5 py-1.5">
          <Search className="w-3.5 h-3.5 text-gray-500" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search semantic layer..."
            className="flex-1 bg-transparent text-xs text-white placeholder-gray-500 outline-none"
          />
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 px-3 pb-2">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={`flex items-center gap-1 px-2 py-1 rounded text-xs transition-colors ${
              activeTab === tab.key
                ? "bg-indigo-600/20 text-indigo-400"
                : "text-gray-500 hover:text-gray-300 hover:bg-gray-800"
            }`}
          >
            {tab.icon}
            {tab.label}
            <span className="text-gray-600 ml-0.5">{tab.count}</span>
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-3 pb-3 scrollbar-thin">
        {activeTab === "columns" && (
          <ColumnsView
            columns={data.column_descriptions}
            dimensions={data.dimensions}
            filterText={filterText}
            expandedTables={expandedTables}
            onToggleTable={toggleTable}
          />
        )}
        {activeTab === "glossary" && (
          <GlossaryView glossary={data.glossary} filterText={filterText} />
        )}
        {activeTab === "metrics" && (
          <MetricsView metrics={data.metrics} filterText={filterText} />
        )}
        {activeTab === "filters" && (
          <FiltersView filters={data.filters} filterText={filterText} />
        )}
        {activeTab === "joins" && (
          <JoinsView joins={data.joins} filterText={filterText} />
        )}
        {activeTab === "trusted" && (
          <TrustedQueriesView
            queries={data.trusted_queries}
            filterText={filterText}
            onAskQuestion={onAskQuestion}
          />
        )}
      </div>
    </div>
  );
}

function ColumnsView({
  columns,
  dimensions,
  filterText,
  expandedTables,
  onToggleTable,
}: {
  columns: SemanticColumnDescription[];
  dimensions: SemanticDimension[];
  filterText: string;
  expandedTables: Set<string>;
  onToggleTable: (t: string) => void;
}) {
  const dimSet = new Set(dimensions.map((d) => `${d.table_name}.${d.column_name}`));
  const tables = [...new Set(columns.map((c) => c.table_name))];

  return (
    <div className="space-y-2">
      {tables.map((table) => {
        const tableCols = columns.filter(
          (c) =>
            c.table_name === table &&
            (filterText === "" ||
              c.column_name.toLowerCase().includes(filterText) ||
              c.description.toLowerCase().includes(filterText) ||
              (c.business_name || "").toLowerCase().includes(filterText))
        );
        if (tableCols.length === 0 && filterText) return null;

        const isExpanded = expandedTables.has(table);
        return (
          <div key={table} className="bg-gray-800/50 rounded-lg overflow-hidden">
            <button
              onClick={() => onToggleTable(table)}
              className="w-full flex items-center gap-2 px-3 py-2 text-xs font-medium text-gray-300 hover:text-white transition-colors"
            >
              {isExpanded ? (
                <ChevronDown className="w-3 h-3" />
              ) : (
                <ChevronRight className="w-3 h-3" />
              )}
              <span className="font-mono text-indigo-400">{table}</span>
              <span className="text-gray-600 ml-auto">{tableCols.length} cols</span>
            </button>
            {isExpanded && (
              <div className="px-3 pb-2 space-y-1.5">
                {tableCols.map((col) => (
                  <div
                    key={`${col.table_name}.${col.column_name}`}
                    className="pl-5 border-l-2 border-gray-700 py-1"
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-mono text-gray-200">
                        {col.column_name}
                      </span>
                      {col.data_format && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400">
                          {col.data_format}
                        </span>
                      )}
                      {dimSet.has(`${col.table_name}.${col.column_name}`) && (
                        <span className="text-xs px-1.5 py-0.5 rounded bg-purple-900/30 text-purple-400">
                          dim
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-gray-500 mt-0.5">{col.description}</p>
                    {col.business_name && (
                      <p className="text-xs text-indigo-400/70 mt-0.5">
                        aka "{col.business_name}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function GlossaryView({
  glossary,
  filterText,
}: {
  glossary: SemanticGlossaryEntry[];
  filterText: string;
}) {
  const filtered = glossary.filter(
    (g) =>
      filterText === "" ||
      g.term.toLowerCase().includes(filterText) ||
      g.definition.toLowerCase().includes(filterText) ||
      (g.synonyms || "").toLowerCase().includes(filterText)
  );

  return (
    <div className="space-y-2">
      {filtered.map((g) => (
        <div key={g.term} className="bg-gray-800/50 rounded-lg px-3 py-2.5">
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-white">{g.term}</span>
            {g.mapped_table && (
              <span className="text-xs text-gray-500">
                → <span className="font-mono text-indigo-400/70">{g.mapped_table}</span>
                {g.mapped_column && (
                  <span className="font-mono text-indigo-400/70">.{g.mapped_column}</span>
                )}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-400 mt-1">{g.definition}</p>
          {g.synonyms && (
            <div className="flex flex-wrap gap-1 mt-1.5">
              {g.synonyms.split(",").map((s) => (
                <span
                  key={s.trim()}
                  className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-400"
                >
                  {s.trim()}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">No glossary entries found.</p>
      )}
    </div>
  );
}

function MetricsView({
  metrics,
  filterText,
}: {
  metrics: SemanticMetric[];
  filterText: string;
}) {
  const filtered = metrics.filter(
    (m) =>
      filterText === "" ||
      m.name.toLowerCase().includes(filterText) ||
      m.description.toLowerCase().includes(filterText) ||
      m.expression.toLowerCase().includes(filterText)
  );

  return (
    <div className="space-y-2">
      {filtered.map((m) => (
        <div key={`${m.name}-${m.table_name}`} className="bg-gray-800/50 rounded-lg px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Calculator className="w-3 h-3 text-amber-400" />
            <span className="text-xs font-semibold text-white">{m.name}</span>
            <span className="text-xs px-1.5 py-0.5 rounded bg-gray-700 text-gray-500">
              {m.format_type}
            </span>
          </div>
          <p className="text-xs text-gray-400 mt-1">{m.description}</p>
          <div className="mt-1.5 bg-gray-900 rounded px-2 py-1">
            <code className="text-xs text-emerald-400 font-mono">{m.expression}</code>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Table: <span className="font-mono text-indigo-400/70">{m.table_name}</span>
          </p>
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">No metrics found.</p>
      )}
    </div>
  );
}

function FiltersView({
  filters,
  filterText,
}: {
  filters: SemanticFilter[];
  filterText: string;
}) {
  const filtered = filters.filter(
    (f) =>
      filterText === "" ||
      f.name.toLowerCase().includes(filterText) ||
      (f.description || "").toLowerCase().includes(filterText) ||
      f.expression.toLowerCase().includes(filterText)
  );

  return (
    <div className="space-y-2">
      {filtered.map((f) => (
        <div key={`${f.name}-${f.table_name}`} className="bg-gray-800/50 rounded-lg px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Filter className="w-3 h-3 text-cyan-400" />
            <span className="text-xs font-semibold text-white">{f.name}</span>
          </div>
          {f.description && (
            <p className="text-xs text-gray-400 mt-1">{f.description}</p>
          )}
          <div className="mt-1.5 bg-gray-900 rounded px-2 py-1">
            <code className="text-xs text-emerald-400 font-mono">{f.expression}</code>
          </div>
          <p className="text-xs text-gray-600 mt-1">
            Table: <span className="font-mono text-indigo-400/70">{f.table_name}</span>
          </p>
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">No filters found.</p>
      )}
    </div>
  );
}

function JoinsView({
  joins,
  filterText,
}: {
  joins: SemanticJoin[];
  filterText: string;
}) {
  const filtered = joins.filter(
    (j) =>
      filterText === "" ||
      j.left_table.toLowerCase().includes(filterText) ||
      j.right_table.toLowerCase().includes(filterText) ||
      j.on_clause.toLowerCase().includes(filterText)
  );

  return (
    <div className="space-y-2">
      {filtered.map((j) => (
        <div key={`${j.left_table}-${j.right_table}`} className="bg-gray-800/50 rounded-lg px-3 py-2.5">
          <div className="flex items-center gap-2 text-xs">
            <Link2 className="w-3 h-3 text-orange-400" />
            <span className="font-mono text-indigo-400">{j.left_table}</span>
            <span className="text-gray-500">{j.join_type} JOIN</span>
            <span className="font-mono text-indigo-400">{j.right_table}</span>
          </div>
          <div className="mt-1.5 bg-gray-900 rounded px-2 py-1">
            <code className="text-xs text-emerald-400 font-mono">ON {j.on_clause}</code>
          </div>
          {j.description && (
            <p className="text-xs text-gray-400 mt-1">{j.description}</p>
          )}
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">No join relationships found.</p>
      )}
    </div>
  );
}

function TrustedQueriesView({
  queries,
  filterText,
  onAskQuestion,
}: {
  queries: SemanticTrustedQuery[];
  filterText: string;
  onAskQuestion?: (question: string) => void;
}) {
  const filtered = queries.filter(
    (q) =>
      filterText === "" ||
      q.question.toLowerCase().includes(filterText) ||
      q.sql_query.toLowerCase().includes(filterText) ||
      (q.description || "").toLowerCase().includes(filterText)
  );

  return (
    <div className="space-y-2">
      {filtered.map((q) => (
        <div key={q.question} className="bg-gray-800/50 rounded-lg px-3 py-2.5">
          <button
            onClick={() => onAskQuestion?.(q.question)}
            className="text-left w-full group"
          >
            <div className="flex items-start gap-2">
              <FileCode className="w-3 h-3 text-green-400 mt-0.5 flex-shrink-0" />
              <span className="text-xs font-medium text-gray-200 group-hover:text-indigo-400 transition-colors">
                {q.question}
              </span>
            </div>
          </button>
          {q.description && (
            <p className="text-xs text-gray-500 mt-1 ml-5">{q.description}</p>
          )}
          <div className="mt-1.5 bg-gray-900 rounded px-2 py-1 ml-5">
            <code className="text-xs text-emerald-400 font-mono break-all">
              {q.sql_query}
            </code>
          </div>
          {q.table_name && (
            <p className="text-xs text-gray-600 mt-1 ml-5">
              Table: <span className="font-mono text-indigo-400/70">{q.table_name}</span>
            </p>
          )}
        </div>
      ))}
      {filtered.length === 0 && (
        <p className="text-xs text-gray-600 text-center py-4">No trusted queries found.</p>
      )}
    </div>
  );
}
