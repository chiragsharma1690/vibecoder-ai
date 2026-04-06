import { useState, FormEvent } from 'react';
import { Hash, X } from 'lucide-react';
import { apiService } from '../../services/api';
import { Button } from '../atoms/Button';
import { Input } from '../atoms/Input';

interface SlackLinkModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const SlackLinkModal = ({ isOpen, onClose }: SlackLinkModalProps) => {
  const [slackId, setSlackId] = useState('');
  const [isLinking, setIsLinking] = useState(false);
  const [slackMessage, setSlackMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  if (!isOpen) return null;

  const handleLinkSlack = async (e: FormEvent) => {
    e.preventDefault();
    if (!slackId.trim()) return;
    setIsLinking(true);
    setSlackMessage(null);

    try {
      await apiService.linkSlack({ slack_user_id: slackId.trim() });
      setSlackMessage({ type: 'success', text: 'Successfully linked to database!' });
      setTimeout(() => {
        onClose();
        setSlackMessage(null);
        setSlackId('');
      }, 2000);
    } catch (err: any) {
      setSlackMessage({ type: 'error', text: err.response?.data?.detail || 'Failed to link account.' });
    } finally {
      setIsLinking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/50 backdrop-blur-sm animate-fade-in px-4">
      <div className="bg-white dark:bg-zinc-900 border border-gray-200 dark:border-zinc-800 rounded-2xl w-full max-w-md p-6 shadow-2xl animate-slide-up">
        
        {/* Modal Header */}
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Hash className="text-indigo-600 dark:text-indigo-400" /> Link Slack Account
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-900 dark:hover:text-white transition-colors">
            <X size={20} />
          </button>
        </div>

        {/* Status Message */}
        {slackMessage && (
          <div className={`mb-4 p-3 rounded-lg text-sm border ${
            slackMessage.type === 'success' 
              ? 'bg-emerald-50 dark:bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-500/20' 
              : 'bg-red-50 dark:bg-red-500/10 text-red-700 dark:text-red-400 border-red-200 dark:border-red-500/20'
          }`}>
            {slackMessage.text}
          </div>
        )}

        {/* Link Form */}
        <form onSubmit={handleLinkSlack} className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-zinc-400">
            To trigger AI agents from Slack, enter your Slack Member ID (e.g., U12345678). You can find this in Slack by viewing your profile and clicking "Copy Member ID".
          </p>
          <Input 
            required 
            placeholder="e.g. U012345678" 
            value={slackId} 
            onChange={(e) => setSlackId(e.target.value)} 
            disabled={isLinking}
          />
          <Button type="submit" className="w-full" isLoading={isLinking}>
            Save to Database
          </Button>
        </form>

      </div>
    </div>
  );
};