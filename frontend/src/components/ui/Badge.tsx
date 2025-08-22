import React from 'react';

interface Props {
  children: React.ReactNode;
}

export default function Badge({ children }: Props) {
  return (
    <span style={{ padding: '0.25rem 0.5rem', border: '1px solid var(--color-border)' }}>
      {children}
    </span>
  );
}
