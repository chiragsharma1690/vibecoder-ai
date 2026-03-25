import { useState, useEffect } from 'react';
import axios from 'axios';
import { Loader2, Github, Trello, GitBranch } from 'lucide-react';

export default function SetupForm({ onConnect }) {
  const [step, setStep] = useState(1);
  const [formData, setFormData] = useState({
    jira_url: '', jira_user: '', jira_token: '', github_token: '', repo_url: ''
  });
  
  const [availableBranches, setAvailableBranches] = useState([]);
  const [selectedBranch, setSelectedBranch] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const saved = localStorage.getItem('vibeCoderCreds');
    if (saved) setFormData(JSON.parse(saved));
  }, []);

  const handleChange = (e) => setFormData({ ...formData, [e.target.name]: e.target.value });

  // STEP 1: Connect and fetch branches
  const handleConnect = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      const response = await axios.post('http://localhost:8000/api/connect', formData);
      localStorage.setItem('vibeCoderCreds', JSON.stringify(formData));
      
      setAvailableBranches(response.data.branches);
      setSelectedBranch(response.data.branches[0] || 'main');
      setStep(2); // Move to branch selection
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect. Check backend logs.');
    } finally {
      setIsLoading(false);
    }
  };

  // STEP 2: Set the base branch and launch
  const handleSetBranch = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);

    try {
      await axios.post('http://localhost:8000/api/set-branch', { branch_name: selectedBranch });
      const repoName = formData.repo_url.split('/').pop().replace('.git', '');
      onConnect(`${repoName} (${selectedBranch})`);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to set branch.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto mt-10 p-8 bg-slate-800 border border-slate-700 rounded-xl shadow-2xl">
      <div className="text-center mb-8">
        <h2 className="text-2xl font-bold text-white mb-2">Initialize Workspace</h2>
        <p className="text-slate-400 text-sm">
          {step === 1 ? "Provide your credentials to clone your repo." : "Select the base branch for the AI agent to work from."}
        </p>
      </div>

      {error && <div className="mb-4 p-3 bg-red-900/30 border border-red-500/50 rounded-lg text-red-400 text-sm">{error}</div>}

      {step === 1 ? (
        <form onSubmit={handleConnect} className="space-y-6">
          {/* Keep your existing Jira and GitHub input fields here! For brevity, I am summarizing them: */}
          <div className="space-y-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700/50">
            <h3 className="flex items-center gap-2 text-blue-400 font-medium"><Trello size={18}/> Jira Config</h3>
            <input required type="url" name="jira_url" value={formData.jira_url} onChange={handleChange} placeholder="Jira URL" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
            <div className="grid grid-cols-2 gap-4">
              <input required type="email" name="jira_user" value={formData.jira_user} onChange={handleChange} placeholder="Jira Email" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
              <input required type="password" name="jira_token" value={formData.jira_token} onChange={handleChange} placeholder="Jira Token" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
            </div>
          </div>

          <div className="space-y-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700/50">
            <h3 className="flex items-center gap-2 text-emerald-400 font-medium"><Github size={18}/> GitHub Config</h3>
            <input required type="password" name="github_token" value={formData.github_token} onChange={handleChange} placeholder="GitHub Token" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
            <input required type="url" name="repo_url" value={formData.repo_url} onChange={handleChange} placeholder="Repo URL" className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-2 text-white" />
          </div>

          <button type="submit" disabled={isLoading} className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50">
            {isLoading ? <><Loader2 className="animate-spin" size={20} /> Connecting...</> : 'Connect & Fetch Branches'}
          </button>
        </form>
      ) : (
        <form onSubmit={handleSetBranch} className="space-y-6">
          <div className="space-y-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700/50">
             <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-1">
               <GitBranch size={18} className="text-purple-400" /> 
               Select Target Branch
             </label>
             <select 
               value={selectedBranch} 
               onChange={(e) => setSelectedBranch(e.target.value)}
               className="w-full bg-slate-900 border border-slate-600 rounded-lg px-4 py-3 text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
             >
               {availableBranches.map(branch => (
                 <option key={branch} value={branch}>{branch}</option>
               ))}
             </select>
          </div>

          <button type="submit" disabled={isLoading} className="w-full bg-purple-600 hover:bg-purple-700 text-white font-medium py-3 rounded-lg flex items-center justify-center gap-2 disabled:opacity-50">
            {isLoading ? <><Loader2 className="animate-spin" size={20} /> Checking out...</> : 'Launch AI Agent'}
          </button>
        </form>
      )}
    </div>
  );
}