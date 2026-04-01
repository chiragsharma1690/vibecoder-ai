import { useState } from 'react';
import { CheckCircle2, FilePlus, Terminal, RefreshCw } from 'lucide-react';
import { PlanData } from '../../types';
import { Button } from '../atoms/Button';
import { TextArea } from '../atoms/TextArea';

interface PlanCardProps {
  plan: PlanData;
  isProcessing: boolean;
  onApprove: (asyncMode: boolean) => void;
  onModify: (feedback: string) => void;
}

export const PlanCard = ({ plan, isProcessing, onApprove, onModify }: PlanCardProps) => {
  const [feedback, setFeedback] = useState('');
  const [asyncMode, setAsyncMode] = useState(true);

  return (
    <div className="bg-white dark:bg-zinc-900/80 border border-gray-200 dark:border-zinc-800 rounded-xl p-6 mt-2 shadow-xl w-full max-w-3xl animate-slide-up backdrop-blur-sm transition-colors duration-300">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-zinc-100 mb-4 transition-colors">Proposed Architecture</h3>
      
      <div className="space-y-6">
        <div>
          <span className="text-[10px] font-bold text-gray-500 dark:text-zinc-500 uppercase tracking-widest transition-colors">Strategy</span>
          <p className="text-gray-700 dark:text-zinc-300 text-sm mt-1.5 leading-relaxed transition-colors">{plan.strategy}</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="bg-gray-50 dark:bg-zinc-950/50 p-4 rounded-lg border border-gray-200 dark:border-zinc-800/50 transition-colors duration-300">
             <div className="flex items-center gap-2 mb-3">
                <FilePlus size={16} className="text-indigo-600 dark:text-indigo-400" />
                <span className="text-sm font-medium text-gray-800 dark:text-zinc-200 transition-colors">Files Affected</span>
             </div>
             <ul className="text-xs text-gray-600 dark:text-zinc-400 space-y-1.5 font-mono transition-colors">
               {plan.files_to_modify?.map(f => <li key={f} className="text-amber-600 dark:text-amber-400/90 truncate">~ {f}</li>)}
               {plan.new_files?.map(f => <li key={f} className="text-emerald-600 dark:text-emerald-400/90 truncate">+ {f}</li>)}
               {(!plan.files_to_modify?.length && !plan.new_files?.length) && <li className="text-gray-400 dark:text-zinc-600">None</li>}
             </ul>
          </div>

          <div className="bg-gray-50 dark:bg-zinc-950/50 p-4 rounded-lg border border-gray-200 dark:border-zinc-800/50 transition-colors duration-300">
             <div className="flex items-center gap-2 mb-3">
                <Terminal size={16} className="text-purple-600 dark:text-purple-400" />
                <span className="text-sm font-medium text-gray-800 dark:text-zinc-200 transition-colors">Commands</span>
             </div>
             <ul className="text-xs text-gray-600 dark:text-zinc-400 space-y-1.5 font-mono transition-colors">
               {plan.commands_to_run?.map(cmd => <li key={cmd} className="truncate">$ {cmd}</li>)}
               {!plan.commands_to_run?.length && <li className="text-gray-400 dark:text-zinc-600">None</li>}
             </ul>
          </div>
        </div>
        
        <div className="pt-6 border-t border-gray-200 dark:border-zinc-800/80 space-y-5 transition-colors">
          <TextArea
            label="REVISE PLAN (OPTIONAL)"
            value={feedback}
            onChange={(e) => setFeedback(e.target.value)}
            disabled={isProcessing}
            placeholder="E.g., Don't use standard CSS, use Tailwind classes instead..."
            rows={2}
          />
          
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <label className="flex items-center gap-2.5 cursor-pointer group">
              <input 
                type="checkbox" 
                checked={asyncMode} 
                onChange={(e) => setAsyncMode(e.target.checked)}
                disabled={isProcessing}
                className="w-4 h-4 text-indigo-600 dark:text-indigo-500 rounded bg-white dark:bg-zinc-900 border-gray-300 dark:border-zinc-700 focus:ring-indigo-500/50 dark:focus:ring-offset-zinc-950 transition-colors"
              />
              <span className="text-sm font-medium text-gray-600 dark:text-zinc-400 group-hover:text-gray-900 dark:group-hover:text-zinc-300 transition-colors">
                Async Mode (Auto-PR)
              </span>
            </label>

            <div className="flex gap-3 w-full sm:w-auto">
              <Button 
                variant="secondary"
                onClick={() => onModify(feedback)} 
                disabled={isProcessing || !feedback.trim()}
                icon={<RefreshCw size={16} />}
              >
                Revise
              </Button>
              
              <Button 
                variant="primary"
                onClick={() => onApprove(asyncMode)}
                isLoading={isProcessing}
                icon={!isProcessing && <CheckCircle2 size={16} />}
              >
                {asyncMode ? 'Dispatch AI' : 'Approve & Code'}
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};