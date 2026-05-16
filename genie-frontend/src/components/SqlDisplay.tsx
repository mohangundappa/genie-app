import { useState } from "react";
import { Copy, Check } from "lucide-react";

interface SqlDisplayProps {
  sql: string;
  explanation?: string;
}

export function SqlDisplay({ sql, explanation }: SqlDisplayProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(sql);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!sql) return null;

  return (
    <div className="rounded-lg border border-gray-700 overflow-hidden">
      <div className="flex items-center justify-between bg-gray-800 px-4 py-2">
        <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
          Generated SQL
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="p-4 bg-gray-900 text-sm text-indigo-300 overflow-x-auto font-mono leading-relaxed">
        {formatSql(sql)}
      </pre>
      {explanation && (
        <div className="px-4 py-2.5 bg-gray-800/50 border-t border-gray-700 text-xs text-gray-400">
          {explanation}
        </div>
      )}
    </div>
  );
}

function formatSql(sql: string): string {
  return sql
    .replace(/\b(SELECT|FROM|WHERE|GROUP BY|ORDER BY|HAVING|LIMIT|JOIN|LEFT JOIN|RIGHT JOIN|INNER JOIN|ON|AND|OR|AS|IN|NOT|BETWEEN|LIKE|IS|NULL|COUNT|SUM|AVG|MIN|MAX|ROUND|DISTINCT|UNION|WITH|INSERT|UPDATE|DELETE|CREATE|DROP|ALTER|DESC|ASC)\b/gi, (match) => match.toUpperCase())
    .trim();
}
