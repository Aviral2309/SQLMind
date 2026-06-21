export default function ResultsTable({ columns, rows }) {
  if (!columns?.length || !rows?.length) return null

  return (
    <div className="overflow-x-auto max-h-96">
      <table className="w-full text-sm">
        <thead className="sticky top-0 bg-gray-800">
          <tr>
            {columns.map(col => (
              <th key={col} className="text-left text-xs text-gray-400 font-medium px-4 py-2.5 border-b border-gray-700 whitespace-nowrap">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-gray-800 hover:bg-gray-800/40 transition-colors">
              {row.map((cell, ci) => (
                <td key={ci} className="px-4 py-2.5 text-gray-300 font-mono text-xs whitespace-nowrap max-w-xs truncate">
                  {cell === null ? <span className="text-gray-600">NULL</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
