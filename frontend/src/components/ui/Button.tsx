import React from 'react';

interface Props extends React.ButtonHTMLAttributes<HTMLButtonElement> {}

export const Button: React.FC<Props> = ({ children, ...props }) => (
  <button
    className="px-3 py-1 border border-gray-400 bg-gray-100 hover:bg-gray-200"
    {...props}
  >
    {children}
  </button>
);
