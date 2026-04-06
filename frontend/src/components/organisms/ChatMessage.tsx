import { Bot, User, GitCommit } from 'lucide-react';
import { PlanCard } from './PlanCard';
import { DiffCard } from './DiffCard';
import { Message } from '../../types';
import { Button } from '../atoms/Button';
import { Spinner } from '../atoms/Spinner';

interface ChatMessageProps {
  msg: Message;
  isProcessing: boolean;
  onExecute: (ticketId: string, plan: any, asyncMode: boolean) => void;
  onModify: (ticketId: string, previousPlan: any, feedback: string) => void;
  onPush: (ticketId: string) => void;
}

export const ChatMessage = ({ msg, isProcessing, onExecute, onModify, onPush }: ChatMessageProps) => {
  const isUser = msg.role === 'user';
  const isSystem = msg.role === 'system';

  if (isSystem) {
    return (
      <div className="flex justify-center my-4 animate-fade-in">
        <div className={`px-4 py-2 rounded-full border text-xs font-medium flex items-center gap-2 shadow-sm transition-colors duration-300 ${
          msg.type === 'error' 
            ? 'bg-red-50 border-red-200 text-red-600 dark:bg-red-500/10 dark:border-red-500/20 dark:text-red-400' 
            : 'bg-gray-100 border-gray-200 text-gray-600 dark:bg-zinc-900/50 dark:border-zinc-800 dark:text-zinc-400'
        }`}>
          {msg.type !== 'error' && isProcessing && <Spinner size={12} />}
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-4 w-full animate-fade-in ${isUser ? 'justify-end' : 'justify-start'}`}>
      
      {/* Bot Avatar */}
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 dark:bg-indigo-500/10 dark:border-indigo-500/20 flex items-center justify-center shrink-0 mt-1 shadow-sm transition-colors duration-300">
          <Bot size={18} className="text-indigo-600 dark:text-indigo-400" />
        </div>
      )}

      <div className={`max-w-[85%] ${isUser ? 'order-1' : 'order-2'}`}>
        
        {/* User Message */}
        {isUser && (
          <div className="bg-indigo-600 text-white dark:bg-zinc-800 dark:text-zinc-100 px-5 py-2.5 rounded-2xl rounded-tr-sm inline-block whitespace-pre-wrap text-sm shadow-sm border border-indigo-700 dark:border-zinc-700/50 transition-colors duration-300">
            {msg.content}
          </div>
        )}

        {/* Bot Standard Text */}
        {!isUser && msg.type === 'text' && (
          <div className="text-gray-800 dark:text-zinc-300 px-2 py-1 inline-block whitespace-pre-wrap text-sm leading-relaxed transition-colors duration-300">
            {msg.content}
          </div>
        )}

        {/* Bot Plan Card */}
        {msg.type === 'plan' && msg.plan && msg.ticketId && (
          <PlanCard 
            plan={msg.plan} 
            isProcessing={isProcessing} 
            onApprove={(asyncMode) => onExecute(msg.ticketId!, msg.plan, asyncMode)}
            onModify={(feedback) => onModify(msg.ticketId!, msg.plan, feedback)}
          />
        )}

        {/* Bot Action Card */}
        {msg.type === 'action' && (
          <div className="mt-2 w-full">
            <div className="bg-white dark:bg-zinc-900/80 border border-gray-200 dark:border-zinc-800 text-gray-800 dark:text-zinc-200 p-5 rounded-xl shadow-lg mb-4 backdrop-blur-sm transition-colors duration-300">
              <p className="mb-4 text-emerald-600 dark:text-emerald-400 font-medium text-sm">{msg.content}</p>
              <Button 
                variant="primary"
                onClick={() => msg.ticketId && onPush(msg.ticketId)}
                isLoading={isProcessing}
                icon={<GitCommit size={16} />}
              >
                Approve & Push to GitHub
              </Button>
            </div>
            {msg.fileDiffs && <DiffCard diffs={msg.fileDiffs} />}
          </div>
        )}
      </div>

      {/* User Avatar */}
      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-gray-100 border border-gray-200 dark:bg-zinc-800 dark:border-zinc-700 flex items-center justify-center shrink-0 mt-1 order-2 shadow-sm transition-colors duration-300">
          <User size={18} className="text-gray-500 dark:text-zinc-400" />
        </div>
      )}
    </div>
  );
};