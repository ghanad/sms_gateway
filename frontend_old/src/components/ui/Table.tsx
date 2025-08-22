import React from 'react';

interface TableProps {
  headers: string[];
  rows: React.ReactNode[][];
}

export const Table: React.FC<TableProps> = ({ headers, rows }) => (
  <table className="w-full border-collapse">
    <thead>
      <tr>
        {headers.map((h) => (
          <th key={h} className="border-b border-gray-300 text-left p-2">
            {h}
          </th>
        ))}
      </tr>
    </thead>
    <tbody>
      {rows.map((row, i) => (
        <tr key={i} className="hover:bg-gray-50">
          {row.map((cell, j) => (
            <td key={j} className="border-b border-gray-200 p-2">
              {cell}
            </td>
          ))}
        </tr>
      ))}
    </tbody>
  </table>
);
