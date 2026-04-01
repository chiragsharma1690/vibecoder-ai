import React, { useEffect, useState } from 'react';
import { Bot, LogOut, Sun, Moon } from 'lucide-react';

interface MainLayoutProps {
  children: React.ReactNode;
  isConnected: boolean;
  workspaceInfo: string | null;
  onDisconnect?: () => void;
}

export const MainLayout = ({ children, isConnected, workspaceInfo, onDisconnect }: MainLayoutProps) => {

  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') !== 'light';
    }
    return true;
  });

  useEffect(() => {
    const root = window.document.documentElement;
    if (isDark) {
      root.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      root.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDark]);

  return (
    <div className="min-h-screen flex flex-col font-sans bg-gray-50 dark:bg-zinc-950 text-gray-900 dark:text-zinc-100 transition-colors duration-300">
      
      <header className="sticky top-0 z-50 w-full border-b border-gray-200 dark:border-white/5 bg-white/80 dark:bg-zinc-950/80 backdrop-blur-xl transition-colors duration-300">
        <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
          
          <div className="flex items-center gap-3 select-none">
            <div className="p-1.5 bg-indigo-500/10 rounded-lg border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.15)]">
              <Bot size={22} className="text-indigo-500 dark:text-indigo-400" />
            </div>
            <h1 className="text-lg font-semibold tracking-tight">
              VibeCoder <span className="text-gray-500 dark:text-zinc-500 font-normal">AI</span>
            </h1>
          </div>
          
          <div className="flex items-center gap-4 animate-fade-in">
            {/* THEME TOGGLE BUTTON */}
            <button
              onClick={() => setIsDark(!isDark)}
              className="p-2 text-gray-500 dark:text-zinc-400 hover:bg-gray-100 dark:hover:bg-zinc-800 rounded-full transition-colors"
              title="Toggle Theme"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </button>

            {isConnected && workspaceInfo && (
              <>
                <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-white/10 text-xs font-medium text-gray-600 dark:text-zinc-400 shadow-sm">
                  <span className="relative flex h-2 w-2">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                    <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                  </span>
                  {workspaceInfo}
                </div>
                
                <button 
                  onClick={onDisconnect}
                  className="p-1.5 text-gray-500 dark:text-zinc-500 hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-500/10 rounded-md transition-colors"
                  title="Disconnect Workspace"
                >
                  <LogOut size={16} />
                </button>
              </>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 w-full max-w-5xl mx-auto p-6 flex flex-col relative">
        {children}
      </main>
    </div>
  );
};