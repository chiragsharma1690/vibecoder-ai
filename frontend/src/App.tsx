import { useState } from 'react';
import { MainLayout } from './components/templates/MainLayout';
import { SetupWizard } from './components/organisms/SetupWizard';
import { ChatInterface } from './components/organisms/ChatInterface';

function App() {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [workspaceInfo, setWorkspaceInfo] = useState<string | null>(null);

  const handleConnect = (info: string) => {
    setWorkspaceInfo(info);
    setIsConnected(true);
  };

  return (
    <MainLayout isConnected={isConnected} workspaceInfo={workspaceInfo}>
      {!isConnected ? (
        <SetupWizard onConnect={handleConnect} />
      ) : (
        <div className="flex-1 w-full flex flex-col h-[80vh] animate-fade-in">
          <ChatInterface />
        </div>
      )}
    </MainLayout>
  );
}

export default App;