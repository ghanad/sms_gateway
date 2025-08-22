import React from 'react';

export const Card: React.FC<React.PropsWithChildren> = ({ children }) => (
  <div className="border border-gray-300 p-4 bg-white shadow-sm">{children}</div>
);
