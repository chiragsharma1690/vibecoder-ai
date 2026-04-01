import { useState, useEffect } from 'react';
import { MainLayout } from './components/templates/MainLayout';
import { SetupWizard } from './components/organisms/SetupWizard';
import { ChatInterface } from './components/organisms/ChatInterface';

function App() {
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [workspaceInfo, setWorkspaceInfo] = useState<string | null>(null);

  // Rehydrate session on page reload
  useEffect(() => {
    const savedConfig = localStorage.getItem('vibeCoderCreds');
    const savedBranch = localStorage.getItem('vibeCoderBranch');
    
    if (savedConfig && savedBranch) {
      const parsed = JSON.parse(savedConfig);
      const repoName = parsed.repo_url.split('/').pop()?.replace('.git', '') || 'workspace';
      setWorkspaceInfo(`${repoName} (${savedBranch})`);
      setIsConnected(true);
      
      // We must ensure the cookie is set even after a hard refresh
      const sessionData = { ...parsed, base_branch: savedBranch };
      document.cookie = `vibecoder_session=${btoa(JSON.stringify(sessionData))}; path=/; max-age=86400; SameSite=Strict`;
    }
  }, []);

  const handleConnect = (info: string, branch: string, formData: any) => {
    setWorkspaceInfo(info);
    setIsConnected(true);
    
    // Save to LocalStorage for persistence across reloads
    localStorage.setItem('vibeCoderCreds', JSON.stringify(formData));
    localStorage.setItem('vibeCoderBranch', branch);

    // Bake it into a Base64 Cookie for the backend to read
    const sessionData = { ...formData, base_branch: branch };
    const base64Session = btoa(JSON.stringify(sessionData));
    document.cookie = `vibecoder_session=${base64Session}; path=/; max-age=86400; SameSite=Strict`;
  };

  const handleDisconnect = () => {
    setIsConnected(false);
    setWorkspaceInfo(null);
    // Erase the cookie and local storage
    document.cookie = "vibecoder_session=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;";
    // Note: We leave localStorage('vibeCoderCreds') so the form stays pre-filled, 
    // but you can clear it if you want a hard reset!
  };

  return (
    <MainLayout isConnected={isConnected} workspaceInfo={workspaceInfo} onDisconnect={handleDisconnect}>
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