import { useState, useRef, useEffect, FormEvent } from 'react';
import { Send, Trash2 } from 'lucide-react';
import { apiService } from '../../services/api';
import { ChatMessage } from './ChatMessage';
import { Message } from '../../types';
import { SegmentedControl } from '../molecules/SegmentedControl';
import { Input } from '../atoms/Input';
import { TextArea } from '../atoms/TextArea';
import { Button } from '../atoms/Button';

export const ChatInterface = () => {
  const [messages, setMessages] = useState<Message[]>(() => {
    const saved = localStorage.getItem('vibeCoderChat');
    if (saved) {
      return JSON.parse(saved);
    }
    return [{ role: 'bot', type: 'text', content: 'System initialized. How can I help you build today?' }];
  });
  
  const [mode, setMode] = useState<'existing' | 'new'>('existing');
  const [ticketId, setTicketId] = useState('');
  const [summary, setSummary] = useState('');
  const [description, setDescription] = useState('');
  
  const [isProcessing, setIsProcessing] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    localStorage.setItem('vibeCoderChat', JSON.stringify(messages));
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const clearChat = () => {
    const defaultMsg: Message = { role: 'bot', type: 'text', content: 'System initialized. How can I help you build today?' };
    setMessages([defaultMsg]);
    localStorage.removeItem('vibeCoderChat');
  };

  const addMessage = (msg: Message) => setMessages(prev => [...prev, msg]);

  const handleStartDevelopment = async (e: FormEvent) => {
    e.preventDefault();
    if (isProcessing) return;

    setIsProcessing(true);
    let activeTicketId = ticketId.trim();

    try {
      if (mode === 'new') {
        if (!summary.trim() || !description.trim()) throw new Error("Summary and Description are required.");
        
        addMessage({ role: 'user', type: 'text', content: `Create new feature:\n${summary}\n\n${description}` });
        addMessage({ role: 'system', type: 'text', content: 'Creating new Jira ticket...' });
        
        const response = await apiService.createJiraTicket({ summary, description });
        activeTicketId = response.data.ticket_id;
        
        addMessage({ role: 'system', type: 'text', content: `✅ Created Jira ticket: ${activeTicketId}` });
        setTicketId(activeTicketId); 
        setSummary('');
        setDescription('');
      } else {
        if (!activeTicketId) throw new Error("Ticket ID is required.");
        addMessage({ role: 'user', type: 'text', content: `Work on ticket: ${activeTicketId}` });
      }

      addMessage({ role: 'system', type: 'text', content: `Generating architecture plan for ${activeTicketId}...` });
      const planRes = await apiService.generatePlan({ ticket_id: activeTicketId });
      addMessage({ role: 'bot', type: 'plan', ticketId: activeTicketId, plan: planRes.data.plan });

    } catch (err: any) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || err.message || 'Pipeline failed.' });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleModifyPlan = async (targetTicketId: string, previousPlan: any, feedback: string) => { /* Same as before */
    if (isProcessing || !feedback.trim()) return;
    setIsProcessing(true);
    addMessage({ role: 'user', type: 'text', content: `Feedback: ${feedback}` });
    addMessage({ role: 'system', type: 'text', content: `Revising plan for ${targetTicketId}...` });

    try {
      const res = await apiService.generatePlan({ ticket_id: targetTicketId, feedback, previous_plan: previousPlan });
      addMessage({ role: 'bot', type: 'plan', ticketId: targetTicketId, plan: res.data.plan });
    } catch (err: any) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Failed to revise plan.' });
    } finally {
      setIsProcessing(false);
    }
  };

  const handleExecute = async (targetTicketId: string, plan: any, asyncMode: boolean) => { /* Same as before */
    if (isProcessing) return;
    setIsProcessing(true);
    addMessage({ role: 'system', type: 'text', content: asyncMode ? `Dispatching AI for ${targetTicketId}...` : `Writing code locally for ${targetTicketId}...` });

    try {
      const res = await apiService.executePlan({ ticket_id: targetTicketId, plan, async_mode: asyncMode });
      if (res.data.status === 'async') {
        addMessage({ role: 'bot', type: 'text', content: `🚀 ${res.data.message}` });
      } else {
        addMessage({ role: 'bot', type: 'action', content: `Success! Files modified locally.`, ticketId: targetTicketId, fileDiffs: res.data.file_diffs });
      }
    } catch (err: any) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Execution failed.' });
    } finally {
      setIsProcessing(false);
    }
  };

  const handlePush = async (targetTicketId: string) => { /* Same as before */
    if (isProcessing) return;
    setIsProcessing(true);
    addMessage({ role: 'system', type: 'text', content: `Pushing to GitHub...` });

    try {
      const res = await apiService.pushCode({ ticket_id: targetTicketId });
      addMessage({ role: 'bot', type: 'text', content: `✅ ${res.data.message} (Branch: ${res.data.branch})` });
    } catch (err: any) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Failed to push code.' });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-zinc-950 w-full rounded-2xl overflow-hidden border border-zinc-800/50 shadow-2xl relative">
      
      {/* A subtle Clear Chat button at the top */}
      <div className="absolute top-4 right-6 z-10">
        <button 
          onClick={clearChat}
          className="p-2 bg-zinc-900/80 border border-zinc-800 text-zinc-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg shadow-sm backdrop-blur-sm transition-all flex items-center gap-2 text-xs font-medium"
        >
          <Trash2 size={14} /> Clear History
        </button>
      </div>
      
      {/* Scrollable Chat Area */}
      <div className="flex-1 overflow-y-auto p-6 space-y-8 pb-48 custom-scrollbar">
        {messages.map((msg, idx) => (
          <ChatMessage key={idx} msg={msg} isProcessing={isProcessing} onExecute={handleExecute} onModify={handleModifyPlan} onPush={handlePush} />
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Floating Prompt Input Box */}
      <div className="absolute bottom-0 left-0 right-0 p-6 bg-gradient-to-t from-zinc-950 via-zinc-950/90 to-transparent pt-12">
        <div className="max-w-3xl mx-auto bg-zinc-900/90 backdrop-blur-md border border-zinc-800 rounded-xl p-4 shadow-2xl transition-all">
          
          <div className="mb-4">
            <SegmentedControl 
              options={[
                { label: 'Existing Ticket', value: 'existing' },
                { label: 'Create New Feature', value: 'new' }
              ]} 
              value={mode} 
              onChange={(val) => setMode(val as 'existing' | 'new')} 
              disabled={isProcessing}
            />
          </div>

          <form onSubmit={handleStartDevelopment}>
            {mode === 'existing' ? (
              <div className="relative flex items-center">
                <input 
                  type="text" 
                  value={ticketId} 
                  onChange={(e) => setTicketId(e.target.value)} 
                  disabled={isProcessing} 
                  placeholder="Enter Jira Ticket ID (e.g., KAN-123)..." 
                  className="w-full bg-transparent border-none py-2 text-zinc-100 placeholder:text-zinc-500 focus:outline-none focus:ring-0 text-sm" 
                />
                <Button type="submit" size="sm" disabled={!ticketId.trim() || isProcessing} icon={<Send size={14} />} />
              </div>
            ) : (
              <div className="flex flex-col gap-3">
                <Input 
                  value={summary} 
                  onChange={(e) => setSummary(e.target.value)} 
                  disabled={isProcessing} 
                  placeholder="Feature summary (e.g. Add dark mode toggle)" 
                  className="bg-zinc-950/50"
                />
                <TextArea 
                  value={description} 
                  onChange={(e) => setDescription(e.target.value)} 
                  disabled={isProcessing} 
                  placeholder="Describe the implementation details for the AI..." 
                  rows={2}
                  className="bg-zinc-950/50"
                />
                <div className="flex justify-end mt-2">
                  <Button type="submit" disabled={!summary.trim() || !description.trim() || isProcessing} icon={<Send size={14} />}>
                    Generate
                  </Button>
                </div>
              </div>
            )}
          </form>
        </div>
      </div>

    </div>
  );
};