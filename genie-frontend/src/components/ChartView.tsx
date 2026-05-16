import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  AreaChart,
  Area,
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from "recharts";
import type { ChartConfig } from "../types";

interface ChartViewProps {
  config: ChartConfig;
  data: Record<string, unknown>[];
}

const COLORS = [
  "#6366f1",
  "#8b5cf6",
  "#a78bfa",
  "#c4b5fd",
  "#22d3ee",
  "#34d399",
  "#fbbf24",
  "#f87171",
  "#fb923c",
  "#a3e635",
];

export function ChartView({ config, data }: ChartViewProps) {
  if (!config || config.chart_type === "none" || data.length === 0) {
    return null;
  }

  const chartData = data.map((row) => {
    const processed: Record<string, unknown> = {};
    for (const key of Object.keys(row)) {
      const val = row[key];
      processed[key] = typeof val === "string" && !isNaN(Number(val)) ? Number(val) : val;
    }
    return processed;
  });

  return (
    <div className="bg-gray-800/50 rounded-lg p-4 border border-gray-700">
      <h3 className="text-sm font-semibold text-gray-300 mb-3">
        {config.chart_title}
      </h3>
      <div className="h-72">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart(config, chartData)}
        </ResponsiveContainer>
      </div>
    </div>
  );
}

function renderChart(config: ChartConfig, data: Record<string, unknown>[]) {
  const { chart_type, x_axis, y_axis } = config;

  switch (chart_type) {
    case "bar":
      return (
        <BarChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={x_axis}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            angle={-35}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
            }}
          />
          <Legend wrapperStyle={{ color: "#9ca3af" }} />
          {y_axis.map((key, i) => (
            <Bar key={key} dataKey={key} fill={COLORS[i % COLORS.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      );

    case "line":
      return (
        <LineChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={x_axis}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            angle={-35}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
            }}
          />
          <Legend wrapperStyle={{ color: "#9ca3af" }} />
          {y_axis.map((key, i) => (
            <Line
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              strokeWidth={2}
              dot={{ fill: COLORS[i % COLORS.length], r: 4 }}
            />
          ))}
        </LineChart>
      );

    case "pie":
      return (
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={true}
            label={({ name, percent }: { name: string; percent: number }) =>
              `${name} (${(percent * 100).toFixed(0)}%)`
            }
            outerRadius={90}
            dataKey={y_axis[0]}
            nameKey={x_axis}
          >
            {data.map((_, index) => (
              <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
            }}
          />
        </PieChart>
      );

    case "area":
      return (
        <AreaChart data={data} margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={x_axis}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            angle={-35}
            textAnchor="end"
            height={60}
          />
          <YAxis tick={{ fill: "#9ca3af", fontSize: 11 }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
            }}
          />
          <Legend wrapperStyle={{ color: "#9ca3af" }} />
          {y_axis.map((key, i) => (
            <Area
              key={key}
              type="monotone"
              dataKey={key}
              stroke={COLORS[i % COLORS.length]}
              fill={COLORS[i % COLORS.length]}
              fillOpacity={0.2}
            />
          ))}
        </AreaChart>
      );

    case "scatter":
      return (
        <ScatterChart margin={{ top: 5, right: 30, left: 20, bottom: 60 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis
            dataKey={x_axis}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            name={x_axis}
          />
          <YAxis
            dataKey={y_axis[0]}
            tick={{ fill: "#9ca3af", fontSize: 11 }}
            name={y_axis[0]}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "#1f2937",
              border: "1px solid #374151",
              borderRadius: "8px",
              color: "#e5e7eb",
            }}
          />
          <Scatter name="Data" data={data} fill={COLORS[0]} />
        </ScatterChart>
      );

    default:
      return <div>Unsupported chart type</div>;
  }
}
