import React from 'react';
import { Bot } from 'lucide-react';
import { cn } from '../../utils/cn';

interface MainLayoutProps {
  children: React.ReactNode;
  isConnected: boolean;
  workspaceInfo: string | null;
}

export const MainLayout = ({ children, isConnected, workspaceInfo }: MainLayoutProps) => {
  return (
    <div className="min-h-screen flex flex-col font-sans bg-zinc-950">
      {/* Frosted Glass Header */}
      <header className="sticky top-0 z-50 w-full border-b border-white/5 bg-zinc-950/80 backdrop-blur-xl">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          
          {/* Logo & Branding */}
          <div className="flex items-center gap-3 select-none">
            <div className="p-1.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
              <Bot size={22} className="text-indigo-400" />
            </div>
            <h1 className="text-lg font-semibold tracking-tight text-zinc-100">
              VibeCoder <span className="text-zinc-500 font-normal">AI</span>
            </h1>
          </div>
          
          {/* Active Connection Status */}
          {isConnected && workspaceInfo && (
            <div className="animate-fade-in flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/5 border border-white/10 text-xs font-medium text-zinc-400 shadow-sm">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              {workspaceInfo}
            </div>
          )}
        </div>
      </header>

      {/* Main Content Canvas */}
      <main className="flex-1 w-full max-w-5xl mx-auto p-6 flex flex-col relative">
        {children}
      </main>
    </div>
  );
};