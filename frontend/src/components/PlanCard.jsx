import { CheckCircle2, FilePlus, PlayCircle } from 'lucide-react';

export default function PlanCard({ plan, onApprove, isProcessing }) {
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
          {/* Files to Modify/Create */}
          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <FilePlus size={16} className="text-blue-400" />
                <span className="text-sm font-semibold text-slate-200">Files Affected</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.files_to_modify?.map(f => <li key={f} className="text-yellow-400/90">~ {f}</li>)}
               {plan.new_files?.map(f => <li key={f} className="text-emerald-400/90">+ {f}</li>)}
               {!plan.files_to_modify?.length && !plan.new_files?.length && <li>No files listed.</li>}
             </ul>
          </div>

          {/* Commands to Run */}
          <div className="bg-slate-800/50 p-3 rounded-md border border-slate-700">
             <div className="flex items-center gap-2 mb-2">
                <PlayCircle size={16} className="text-purple-400" />
                <span className="text-sm font-semibold text-slate-200">Commands</span>
             </div>
             <ul className="text-xs text-slate-400 space-y-1 font-mono">
               {plan.commands_to_run?.map(cmd => <li key={cmd}>$ {cmd}</li>)}
               {!plan.commands_to_run?.length && <li>No commands needed.</li>}
             </ul>
          </div>
        </div>
        
        {/* Actions */}
        <div className="pt-3 border-t border-slate-700 flex justify-end">
          <button 
            onClick={onApprove}
            disabled={isProcessing}
            className="flex items-center gap-2 bg-emerald-600 hover:bg-emerald-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <CheckCircle2 size={16} />
            {isProcessing ? 'Executing Plan...' : 'Approve & Execute'}
          </button>
        </div>
      </div>
    </div>
  );
}