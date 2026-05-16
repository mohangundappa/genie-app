import { useState, useEffect } from "react";
import { Database, Table, ChevronRight, Rows3 } from "lucide-react";
import { useApi } from "../hooks/useApi";
import type { Dataset } from "../types";

interface DatasetExplorerProps {
  onSelectDataset?: (name: string) => void;
}

export function DatasetExplorer({ onSelectDataset }: DatasetExplorerProps) {
  const api = useApi();
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getDatasets().then((res) => {
      setDatasets(res.datasets);
      setLoading(false);
    });
  }, []);

  const toggleExpand = (name: string) => {
    setExpanded(expanded === name ? null : name);
  };

  const formatTableName = (name: string) => {
    return name
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  };

  if (loading) {
    return (
      <div className="p-4">
        <div className="animate-pulse space-y-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="h-10 bg-gray-700 rounded" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-1">
      <div className="px-4 py-2 flex items-center gap-2 text-xs uppercase tracking-wider text-gray-500 font-semibold">
        <Database className="w-3.5 h-3.5" />
        Datasets
      </div>
      {datasets.map((ds) => (
        <div key={ds.name}>
          <button
            onClick={() => toggleExpand(ds.name)}
            className="w-full flex items-center gap-2 px-4 py-2.5 text-sm text-gray-300 hover:bg-gray-800 hover:text-white transition-colors"
          >
            <ChevronRight
              className={`w-3.5 h-3.5 text-gray-500 transition-transform ${
                expanded === ds.name ? "rotate-90" : ""
              }`}
            />
            <Table className="w-4 h-4 text-indigo-400" />
            <span className="flex-1 text-left truncate">{formatTableName(ds.name)}</span>
            <span className="text-xs text-gray-500 flex items-center gap-1">
              <Rows3 className="w-3 h-3" />
              {ds.row_count.toLocaleString()}
            </span>
          </button>

          {expanded === ds.name && (
            <div className="ml-10 mr-3 mb-2 space-y-0.5">
              {ds.columns.map((col) => (
                <div
                  key={col.name}
                  className="flex items-center justify-between py-1 px-2 text-xs rounded hover:bg-gray-800/50"
                >
                  <span className="text-gray-400 truncate">{col.name}</span>
                  <span className="text-gray-600 font-mono text-xs">{col.type}</span>
                </div>
              ))}
              <button
                onClick={() => onSelectDataset?.(ds.name)}
                className="mt-1 w-full text-xs text-indigo-400 hover:text-indigo-300 py-1.5 px-2 rounded hover:bg-gray-800 transition-colors text-left"
              >
                Ask about this dataset →
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
