import { useState } from 'react';
import { CheckCircle2, FilePlus, PlayCircle, RefreshCw } from 'lucide-react';

export default function PlanCard({ plan, onApprove, onModify, isProcessing }) {
  const [feedback, setFeedback] = useState('');

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
          <textarea 
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={isProcessing}
            placeholder="Request changes to this plan (e.g., 'Do not create a new file, put logic in utils.js')..."
            className="w-full bg-slate-800 border border-slate-600 rounded-md p-2 text-sm text-white focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            rows="2"
          />
          
          <div className="flex justify-end gap-3">
            <button 
              onClick={() => {
                onModify(feedback);
                setFeedback('');
              }}
              disabled={isProcessing || !feedback.trim()}
              className="flex items-center gap-2 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
            >
              <RefreshCw size={16} />
              Modify Plan
            </button>

            <button 
              onClick={onApprove}
              disabled={isProcessing}
              className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50"
            >
              <CheckCircle2 size={16} />
              Approve & Execute
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}