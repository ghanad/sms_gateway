import React from 'react';

interface Props {
  open: boolean;
  onClose: () => void;
  title?: string;
}

export const Modal: React.FC<React.PropsWithChildren<Props>> = ({
  open,
  onClose,
  title,
  children,
}) => {
  if (!open) return null;
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-black/50">
      <div className="bg-white p-4 w-96">
        <div className="flex justify-between items-center mb-2">
          <h2 className="text-lg">{title}</h2>
          <button onClick={onClose}>x</button>
        </div>
        {children}
      </div>
    </div>
  );
};
