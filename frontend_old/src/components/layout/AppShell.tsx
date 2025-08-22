import React from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';

export const AppShell: React.FC<React.PropsWithChildren> = ({ children }) => {
  return (
    <div className="flex h-screen" data-theme="light">
      <Sidebar />
      <div className="flex flex-col flex-1">
        <Topbar />
        <main className="p-4 flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  );
};
