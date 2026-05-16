interface ResultsTableProps {
  columns: string[];
  rows: Record<string, unknown>[];
  maxRows?: number;
}

export function ResultsTable({ columns, rows, maxRows = 100 }: ResultsTableProps) {
  const displayRows = rows.slice(0, maxRows);

  if (columns.length === 0 || rows.length === 0) {
    return (
      <div className="text-center py-8 text-gray-400">
        No results to display
      </div>
    );
  }

  return (
    <div className="overflow-auto max-h-96 rounded-lg border border-gray-700">
      <table className="w-full text-sm text-left">
        <thead className="text-xs uppercase bg-gray-800 text-gray-300 sticky top-0">
          <tr>
            {columns.map((col) => (
              <th key={col} className="px-4 py-3 whitespace-nowrap font-semibold">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {displayRows.map((row, i) => (
            <tr
              key={i}
              className="border-b border-gray-700 hover:bg-gray-800/50 transition-colors"
            >
              {columns.map((col) => (
                <td key={col} className="px-4 py-2.5 whitespace-nowrap text-gray-300">
                  {formatValue(row[col])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > maxRows && (
        <div className="px-4 py-2 bg-gray-800 text-gray-400 text-xs text-center">
          Showing {maxRows} of {rows.length} rows
        </div>
      )}
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") {
    if (Number.isInteger(value) && Math.abs(value) > 999) {
      return value.toLocaleString();
    }
    if (!Number.isInteger(value)) {
      return Number(value).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    }
  }
  return String(value);
}
