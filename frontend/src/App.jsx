import { useState } from 'react';
import { Bot } from 'lucide-react';
import SetupForm from './components/SetupForm';
import ChatInterface from './components/ChatInterface';

function App() {
  const [isConnected, setIsConnected] = useState(false);
  const [workspaceInfo, setWorkspaceInfo] = useState(null);

  return (
    <div className="min-h-screen flex flex-col items-center p-6 bg-slate-900">
      {/* Header */}
      <header className="w-full max-w-4xl flex items-center justify-between py-6 border-b border-slate-700 mb-8">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-600 rounded-lg shadow-lg shadow-blue-500/20">
            <Bot size={28} className="text-white" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-white">VibeCoder AI</h1>
        </div>
        {isConnected && workspaceInfo && (
          <div className="text-sm bg-slate-800 px-4 py-2 rounded-full border border-slate-700 text-slate-300 shadow-inner">
            Connected to: <span className="font-semibold text-blue-400">{workspaceInfo}</span>
          </div>
        )}
      </header>

      {/* Main Content Area */}
      <main className="w-full max-w-4xl flex-1 flex flex-col">
        {!isConnected ? (
          <SetupForm onConnect={(repoName) => {
            setWorkspaceInfo(repoName);
            setIsConnected(true);
          }} />
        ) : (
          <div className="flex-1 border border-slate-700 rounded-xl bg-slate-800 overflow-hidden shadow-2xl flex flex-col">
             <ChatInterface />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;