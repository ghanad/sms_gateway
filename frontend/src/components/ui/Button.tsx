import React from 'react';

type Props = React.ButtonHTMLAttributes<HTMLButtonElement>;

export default function Button({ children, ...props }: Props) {
  return (
    <button
      {...props}
      style={{
        padding: '0.5rem 1rem',
        border: '1px solid var(--color-border)',
        background: 'var(--color-accent)',
        color: '#fff',
        cursor: 'pointer'
      }}
    >
      {children}
    </button>
  );
}
