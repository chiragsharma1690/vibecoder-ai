import { useState } from 'react';
import { CheckCircle2, FilePlus, PlayCircle, RefreshCw } from 'lucide-react';

export default function PlanCard({ plan, onApprove, onModify, isProcessing }) {
  const [feedback, setFeedback] = useState('');
  const [asyncMode, setAsyncMode] = useState(false);

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-lg p-5 mt-2 shadow-lg w-full max-w-2xl">
      <h3 className="text-lg font-semibold text-white mb-3">Proposed Implementation Plan</h3>
      
      <div className="space-y-4">
        {/* Strategy */}
        <div>
          <span className="text-xs font-bold text-slate-400 uppercase tracking-wider">Strategy</span>
          <p className="text-slate-300 text-sm mt-1 leading-relaxed">{plan.strategy}</p>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <FilePlus size={16} className="text-blue-400" />
                <span className="text-sm font-semibold text-slate-200">Files Affected</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.files_to_modify?.map(f => <li key={f} className="text-yellow-400/90">~ {f}</li>)}
               {plan.new_files?.map(f => <li key={f} className="text-emerald-400/90">+ {f}</li>)}
             </ul>
          </div>

          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <PlayCircle size={16} className="text-purple-400" />
                <span className="text-sm font-semibold text-slate-200">Commands</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.commands_to_run?.map(cmd => <li key={cmd}>$ {cmd}</li>)}
             </ul>
          </div>
        </div>
        
        {/* Actions & Feedback */}
        <div className="pt-4 border-t border-slate-700 space-y-3">
          {/* ... feedback textarea ... */}
          
          <div className="flex items-center justify-between mt-4">
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox" 
                checked={asyncMode} 
                onChange={(e) => setAsyncMode(e.target.checked)}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 bg-slate-800 border-slate-600"
              />
              <span className="text-sm text-slate-300">Async Mode (Auto-create PR)</span>
            </label>

            <div className="flex gap-3">
              <button onClick={() => onModify(feedback)} /* ... */>Modify Plan</button>
              
              <button 
                onClick={() => onApprove(asyncMode)} // Pass the mode up to ChatInterface
                disabled={isProcessing}
                className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
              >
                <CheckCircle2 size={16} />
                {asyncMode ? 'Dispatch AI (Async)' : 'Approve & Review Diffs'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}