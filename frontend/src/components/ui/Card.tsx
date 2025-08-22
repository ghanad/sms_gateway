import React from 'react';

interface Props {
  children: React.ReactNode;
}

export default function Card({ children }: Props) {
  return (
    <div style={{ border: '1px solid var(--color-border)', padding: '1rem', marginBottom: '1rem' }}>
      {children}
    </div>
  );
}
