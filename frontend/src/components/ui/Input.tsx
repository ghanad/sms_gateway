import React from 'react';

interface Props extends React.InputHTMLAttributes<HTMLInputElement> {}

export const Input: React.FC<Props> = (props) => (
  <input
    className="border border-gray-400 px-2 py-1 w-full"
    {...props}
  />
);
