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
        <div className={`px-4 py-2 rounded-full border text-xs font-medium flex items-center gap-2 shadow-sm ${
          msg.type === 'error' 
            ? 'bg-red-500/10 border-red-500/20 text-red-400' 
            : 'bg-zinc-900/50 border-zinc-800 text-zinc-400'
        }`}>
          {msg.type !== 'error' && isProcessing && <Spinner size={12} />}
          {msg.content}
        </div>
      </div>
    );
  }

  return (
    <div className={`flex gap-4 w-full animate-fade-in ${isUser ? 'justify-end' : 'justify-start'}`}>
      
      {!isUser && (
        <div className="w-8 h-8 rounded-lg bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center shrink-0 mt-1 shadow-sm">
          <Bot size={18} className="text-indigo-400" />
        </div>
      )}

      <div className={`max-w-[85%] ${isUser ? 'order-1' : 'order-2'}`}>
        
        {isUser && (
          <div className="bg-zinc-800 text-zinc-100 px-5 py-2.5 rounded-2xl rounded-tr-sm inline-block whitespace-pre-wrap text-sm shadow-sm border border-zinc-700/50">
            {msg.content}
          </div>
        )}

        {!isUser && msg.type === 'text' && (
          <div className="text-zinc-300 px-2 py-1 inline-block whitespace-pre-wrap text-sm leading-relaxed">
            {msg.content}
          </div>
        )}

        {msg.type === 'plan' && msg.plan && msg.ticketId && (
          <PlanCard 
            plan={msg.plan} 
            isProcessing={isProcessing} 
            onApprove={(asyncMode) => onExecute(msg.ticketId!, msg.plan, asyncMode)}
            onModify={(feedback) => onModify(msg.ticketId!, msg.plan, feedback)}
          />
        )}

        {msg.type === 'action' && (
          <div className="mt-2 w-full">
            <div className="bg-zinc-900/80 border border-zinc-800 text-zinc-200 p-5 rounded-xl shadow-lg mb-4 backdrop-blur-sm">
              <p className="mb-4 text-emerald-400 font-medium text-sm">{msg.content}</p>
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

      {isUser && (
        <div className="w-8 h-8 rounded-lg bg-zinc-800 border border-zinc-700 flex items-center justify-center shrink-0 mt-1 order-2 shadow-sm">
          <User size={18} className="text-zinc-400" />
        </div>
      )}
    </div>
  );
};