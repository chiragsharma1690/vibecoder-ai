import { useState, useEffect, ChangeEvent, FormEvent } from 'react';
import { GitPullRequest, Kanban, GitBranch, ArrowRight } from 'lucide-react';
import { apiService } from '../../services/api';
import { ConnectFormData } from '../../types';
import { Input } from '../atoms/Input';
import { Button } from '../atoms/Button';

interface SetupWizardProps {
  onConnect: (workspaceInfo: string, branch: string, formData: ConnectFormData) => void;
}

export const SetupWizard = ({ onConnect }: SetupWizardProps) => {
  const [step, setStep] = useState<1 | 2>(1);
  const [formData, setFormData] = useState<ConnectFormData>({
    jira_url: '', jira_user: '', jira_token: '', github_token: '', repo_url: '', jira_project_key: ''
  });
  
  const [availableBranches, setAvailableBranches] = useState<string[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const saved = localStorage.getItem('vibeCoderCreds');
    if (saved) setFormData(JSON.parse(saved));
  }, []);

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleConnect = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiService.connectWorkspace(formData);
      localStorage.setItem('vibeCoderCreds', JSON.stringify(formData));
      
      const base64Session = btoa(JSON.stringify(formData));
      document.cookie = `vibecoder_session=${base64Session}; path=/; max-age=86400; SameSite=Strict`;
      
      setAvailableBranches(response.data.branches);
      setSelectedBranch(response.data.branches[0] || 'main');
      setStep(2);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to connect to workspace.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSetBranch = async (e: FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      await apiService.setBranch({ branch_name: selectedBranch });
      const repoName = formData.repo_url.split('/').pop()?.replace('.git', '') || 'workspace';
      onConnect(`${repoName} (${selectedBranch})`, selectedBranch, formData);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to checkout branch.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-md w-full mx-auto mt-12 animate-slide-up">
      <div className="mb-8 text-center">
        <h2 className="text-2xl font-semibold text-gray-900 dark:text-white tracking-tight mb-2 transition-colors duration-300">
          {step === 1 ? "Connect Workspace" : "Select Branch"}
        </h2>
        <p className="text-gray-500 dark:text-zinc-400 text-sm transition-colors duration-300">
          {step === 1 
            ? "Securely link your Jira and GitHub accounts to begin." 
            : "Choose the foundational branch for your AI to build upon."}
        </p>
      </div>

      {error && (
        <div className="mb-6 p-4 bg-red-50 dark:bg-red-500/10 border border-red-200 dark:border-red-500/20 rounded-xl text-red-600 dark:text-red-400 text-sm animate-fade-in transition-colors duration-300">
          {error}
        </div>
      )}

      <div className="bg-white dark:bg-zinc-900/50 border border-gray-200 dark:border-white/5 rounded-2xl p-6 shadow-xl backdrop-blur-sm transition-colors duration-300">
        {step === 1 ? (
          <form onSubmit={handleConnect} className="space-y-6">
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-medium text-indigo-600 dark:text-indigo-400 mb-2 transition-colors">
                <Kanban size={16}/> Jira Configuration
              </div>
              <Input required type="url" name="jira_url" label="Workspace URL" value={formData.jira_url} onChange={handleChange} placeholder="https://domain.atlassian.net" />
              <div className="grid grid-cols-2 gap-4">
                <Input required type="email" name="jira_user" label="Email" value={formData.jira_user} onChange={handleChange} placeholder="you@company.com" />
                <Input required type="password" name="jira_token" label="API Token" value={formData.jira_token} onChange={handleChange} placeholder="••••••••" />
              </div>
              <Input required type="text" name="jira_project_key" label="Default Project Key" value={formData.jira_project_key} onChange={handleChange} placeholder="e.g. KAN" className="uppercase" />
            </div>

            <div className="h-px w-full bg-gray-200 dark:bg-white/5 my-6 transition-colors duration-300" />

            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-medium text-emerald-600 dark:text-emerald-400 mb-2 transition-colors">
                <GitPullRequest size={16}/> GitHub Configuration
              </div>
              <Input required type="password" name="github_token" label="Personal Access Token" value={formData.github_token} onChange={handleChange} placeholder="ghp_••••••••" />
              <Input required type="url" name="repo_url" label="Repository URL" value={formData.repo_url} onChange={handleChange} placeholder="https://github.com/org/repo" />
            </div>

            <Button type="submit" className="w-full mt-4" size="lg" isLoading={isLoading} icon={<ArrowRight size={18} />}>
              Authenticate
            </Button>
          </form>
        ) : (
          <form onSubmit={handleSetBranch} className="space-y-6 animate-fade-in">
             <div className="space-y-2">
               <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-zinc-300 transition-colors">
                 <GitBranch size={16} className="text-indigo-600 dark:text-indigo-400" /> Target Branch
               </label>
               <select 
                 value={selectedBranch} 
                 onChange={(e) => setSelectedBranch(e.target.value)}
                 className="w-full bg-white dark:bg-zinc-900/80 border border-gray-300 dark:border-zinc-800 rounded-lg px-4 py-3 text-sm text-gray-900 dark:text-zinc-100 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500/50 transition-all cursor-pointer"
               >
                 {availableBranches.map(branch => (
                   <option key={branch} value={branch}>{branch}</option>
                 ))}
               </select>
            </div>

            <Button type="submit" variant="primary" className="w-full" size="lg" isLoading={isLoading}>
              Initialize Agent
            </Button>
          </form>
        )}
      </div>
    </div>
  );
};