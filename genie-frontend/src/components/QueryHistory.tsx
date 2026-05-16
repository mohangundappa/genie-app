import { useState, useEffect } from "react";
import { Clock, Search } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { QueryHistoryItem } from "../types";

interface QueryHistoryProps {
  onSelectQuery: (question: string) => void;
}

export function QueryHistory({ onSelectQuery }: QueryHistoryProps) {
  const api = useApi();
  const [history, setHistory] = useState<QueryHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getHistory(20).then((res) => {
      setHistory(res.history);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-2">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-8 bg-gray-700 rounded" />
          ))}
        </div>
      </div>
    );
  }

  if (history.length === 0) {
    return (
      <div className="px-4 py-6 text-center text-gray-500 text-sm">
        <Clock className="w-8 h-8 mx-auto mb-2 opacity-50" />
        No query history yet
      </div>
    );
  }

  return (
    <div className="space-y-0.5">
      <div className="px-4 py-2 flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 font-semibold">
        <Clock className="w-3.5 h-3.5" />
        Recent Queries
      </div>
      {history.map((item) => (
        <button
          key={item.id}
          onClick={() => onSelectQuery(item.question)}
          className="w-full text-left px-4 py-2 text-sm text-gray-400 hover:text-white hover:bg-gray-800 transition-colors truncate flex items-center gap-2"
        >
          <Search className="w-3.5 h-3.5 flex-shrink-0 text-gray-600" />
          <span className="truncate">{item.question}</span>
        </button>
      ))}
    </div>
  );
}
