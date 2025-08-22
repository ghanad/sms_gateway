import React from 'react';

interface Props {
  children: React.ReactNode;
}

export const Badge: React.FC<Props> = ({ children }) => (
  <span className="px-2 py-1 text-xs border border-gray-400 bg-gray-100">
    {children}
  </span>
);
