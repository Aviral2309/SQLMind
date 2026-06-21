import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts'

const COLORS = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#f97316']

function detectChartType(columns, rows) {
  if (!columns?.length || !rows?.length) return 'bar'
  const dateKeywords = ['date', 'month', 'week', 'day', 'year', 'time', 'created', 'updated']
  const hasDate = columns.some(c => dateKeywords.some(k => c.toLowerCase().includes(k)))
  if (hasDate && columns.length <= 3) return 'line'
  if (columns.length === 2) return 'bar'
  if (columns.length >= 3) return 'bar'
  return 'bar'
}

function isNumeric(val) {
  return val !== null && val !== undefined && !isNaN(Number(val))
}

export default function ResultChart({ columns, rows }) {
  if (!columns?.length || !rows?.length) return null

  const chartType = detectChartType(columns, rows)

  // Find label col (first non-numeric) and value cols (numeric)
  const labelCol = columns.find((c, i) => !isNumeric(rows[0]?.[i])) || columns[0]
  const labelIdx = columns.indexOf(labelCol)
  const valueCols = columns.filter((c, i) => i !== labelIdx && isNumeric(rows[0]?.[i]))

  if (!valueCols.length) {
    return (
      <div className="p-6 text-center text-gray-600 text-sm">
        No numeric columns detected for chart
      </div>
    )
  }

  // Build chart data
  const data = rows.map(row => {
    const point = { label: String(row[labelIdx] ?? '') }
    valueCols.forEach((col, i) => {
      point[col] = Number(row[columns.indexOf(col)]) || 0
    })
    return point
  })

  const commonProps = {
    data,
    margin: { top: 8, right: 16, left: 0, bottom: 8 },
  }

  const axisStyle = { fill: '#6b7280', fontSize: 11 }
  const tooltipStyle = {
    backgroundColor: '#1a1a24',
    border: '1px solid #2a2a38',
    borderRadius: 8,
    color: '#e0e0ee',
    fontSize: 12,
  }

  if (chartType === 'line') {
    return (
      <div className="p-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a38" />
            <XAxis dataKey="label" tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: '#9b9bb0' }} />
            {valueCols.map((col, i) => (
              <Line key={col} type="monotone" dataKey={col}
                stroke={COLORS[i % COLORS.length]} strokeWidth={2} dot={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    )
  }

  if (chartType === 'bar') {
    return (
      <div className="p-4 h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke="#2a2a38" />
            <XAxis dataKey="label" tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: 11, color: '#9b9bb0' }} />
            {valueCols.map((col, i) => (
              <Bar key={col} dataKey={col} fill={COLORS[i % COLORS.length]} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    )
  }

  return null
}
