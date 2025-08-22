import React from 'react';

type Props = React.InputHTMLAttributes<HTMLInputElement>;

export default function Input(props: Props) {
  return (
    <input
      {...props}
      style={{
        padding: '0.5rem',
        border: '1px solid var(--color-border)',
        width: '100%'
      }}
    />
  );
}
