import React from 'react';

interface TableProps {
  headers: string[];
  rows: React.ReactNode[][];
}

export default function Table({ headers, rows }: TableProps) {
  return (
    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          {headers.map(h => (
            <th key={h} style={{ textAlign: 'left', borderBottom: '1px solid var(--color-border)', padding: '0.5rem' }}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j} style={{ padding: '0.5rem', borderBottom: '1px solid var(--color-border)' }}>
                {cell}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
