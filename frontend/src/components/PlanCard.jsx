import { useState } from 'react';
import { CheckCircle2, FilePlus, PlayCircle, RefreshCw, Camera } from 'lucide-react';

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
               {(!plan.files_to_modify?.length && !plan.new_files?.length) && <li className="text-slate-500">None</li>}
             </ul>
          </div>

          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <PlayCircle size={16} className="text-purple-400" />
                <span className="text-sm font-semibold text-slate-200">Commands</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.commands_to_run?.map(cmd => <li key={cmd}>$ {cmd}</li>)}
               {!plan.commands_to_run?.length && <li className="text-slate-500">None</li>}
             </ul>
          </div>
        </div>

        {/* UI Testing Components Display */}
        {plan.ui_components_to_screenshot && plan.ui_components_to_screenshot.length > 0 && (
          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <Camera size={16} className="text-pink-400" />
                <span className="text-sm font-semibold text-slate-200">QA Visual Testing Targets</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.ui_components_to_screenshot.map((comp, idx) => (
                 <li key={idx} className="text-pink-300/90">📸 {comp.route} <span className="text-slate-500">→</span> {comp.selector}</li>
               ))}
             </ul>
          </div>
        )}
        
        {/* Actions & Feedback */}
        <div className="pt-4 border-t border-slate-700 space-y-4">
          
          {/* Missing Textarea Implemented */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Revise Plan (Optional)</label>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              disabled={isProcessing}
              placeholder="E.g., Don't use standard CSS, use Tailwind classes instead..."
              className="w-full bg-slate-950 border border-slate-600 rounded-lg p-3 text-sm text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
              rows={2}
            />
          </div>
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mt-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <input 
                type="checkbox" 
                checked={asyncMode} 
                onChange={(e) => setAsyncMode(e.target.checked)}
                disabled={isProcessing}
                className="w-4 h-4 text-blue-600 rounded focus:ring-blue-500 bg-slate-800 border-slate-600"
              />
              <span className="text-sm font-medium text-slate-300">Async Mode (Auto-PR)</span>
            </label>

            <div className="flex gap-3 w-full sm:w-auto">
              {/* Modify Button */}
              <button 
                onClick={() => onModify(feedback)} 
                disabled={isProcessing || !feedback.trim()}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-slate-700 hover:bg-slate-600 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <RefreshCw size={16} className={isProcessing ? "animate-spin" : ""} />
                Revise
              </button>
              
              {/* Approve Button */}
              <button 
                onClick={() => onApprove(asyncMode)}
                disabled={isProcessing}
                className="flex-1 sm:flex-none flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <CheckCircle2 size={16} />
                {asyncMode ? 'Dispatch AI' : 'Approve & Code'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}