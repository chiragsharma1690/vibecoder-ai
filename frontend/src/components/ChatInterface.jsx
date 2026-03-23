import { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { Send, Bot, User, Loader2, GitCommit } from 'lucide-react';
import PlanCard from './PlanCard';
import DiffCard from './DiffCard';

export default function ChatInterface() {
  const [messages, setMessages] = useState([
    { role: 'bot', type: 'text', content: 'Agent initialized and repository cloned. Enter a Jira ticket ID (e.g., KAN-123) to begin.' }
  ]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const chatEndRef = useRef(null);

  // Auto-scroll to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const addMessage = (msg) => setMessages(prev => [...prev, msg]);

  // Phase 1: Request Plan
  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || isProcessing) return;

    const ticketId = input.trim();
    setInput('');
    addMessage({ role: 'user', type: 'text', content: ticketId });
    setIsProcessing(true);
    addMessage({ role: 'system', type: 'text', content: `Fetching Jira context and generating plan for ${ticketId}...` });

    try {
      const res = await axios.post('http://localhost:8000/api/chat/plan', { ticket_id: ticketId });
      addMessage({ 
        role: 'bot', 
        type: 'plan', 
        ticketId: ticketId,
        plan: res.data.plan 
      });
    } catch (err) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Failed to generate plan.' });
    } finally {
      setIsProcessing(false);
    }
  };

  // Phase 1.5: Modify Existing Plan
  const handleModifyPlan = async (ticketId, previousPlan, feedback) => {
    setIsProcessing(true);
    addMessage({ role: 'user', type: 'text', content: `Feedback: ${feedback}` });
    addMessage({ role: 'system', type: 'text', content: `Asking Architect Agent to revise the plan for ${ticketId}...` });

    try {
      const res = await axios.post('http://localhost:8000/api/chat/plan', { 
        ticket_id: ticketId,
        feedback: feedback,
        previous_plan: previousPlan
      });
      
      addMessage({ 
        role: 'bot', 
        type: 'plan', 
        ticketId: ticketId,
        plan: res.data.plan 
      });
    } catch (err) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Failed to revise plan.' });
    } finally {
      setIsProcessing(false);
    }
  };

  // Phase 2: Execute Plan
  const handleExecute = async (ticketId, plan) => {
    setIsProcessing(true);
    addMessage({ role: 'system', type: 'text', content: `Writing code and running tests for ${ticketId}... This may take a minute.` });

    try {
const res = await axios.post('http://localhost:8000/api/chat/execute', { ticket_id: ticketId, plan: plan });
      
      const successMsg = `Success! ${res.data.files_created.length} files modified. QA tests ${res.data.test_passed ? 'passed' : 'skipped/failed'}.`;
      
      addMessage({ 
        role: 'bot', 
        type: 'action', 
        content: successMsg,
        ticketId: ticketId,
        fileDiffs: res.data.file_diffs // NEW: Save the diffs to state
      });
    } catch (err) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Execution failed.' });
    } finally {
      setIsProcessing(false);
    }
  };

  // Phase 3: Push Code
  const handlePush = async (ticketId) => {
    setIsProcessing(true);
    addMessage({ role: 'system', type: 'text', content: `Pushing changes to GitHub...` });

    try {
      const res = await axios.post('http://localhost:8000/api/chat/push', { ticket_id: ticketId });
      addMessage({ role: 'bot', type: 'text', content: `✅ ${res.data.message} (Branch: ${res.data.branch})` });
    } catch (err) {
      addMessage({ role: 'system', type: 'error', content: err.response?.data?.detail || 'Failed to push code.' });
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-slate-900 w-full rounded-xl overflow-hidden">
      {/* Chat History Container */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            
            {/* Avatar */}
            {msg.role !== 'user' && msg.role !== 'system' && (
              <div className="w-8 h-8 rounded-full bg-blue-600/20 flex items-center justify-center shrink-0">
                <Bot size={18} className="text-blue-400" />
              </div>
            )}

            {/* Message Bubble */}
            <div className={`max-w-[80%] ${msg.role === 'user' ? 'order-1' : 'order-2'}`}>
              
              {/* User Text */}
              {msg.role === 'user' && (
                <div className="bg-blue-600 text-white px-4 py-2 rounded-2xl rounded-tr-sm inline-block">
                  {msg.content}
                </div>
              )}

              {/* System Messages (Loading/Errors) */}
              {msg.role === 'system' && (
                <div className={`text-sm px-4 py-2 rounded-lg border ${msg.type === 'error' ? 'bg-red-900/20 border-red-800 text-red-400' : 'bg-slate-800 border-slate-700 text-slate-400'} flex items-center gap-2`}>
                  {msg.type !== 'error' && isProcessing && <Loader2 size={14} className="animate-spin" />}
                  {msg.content}
                </div>
              )}

              {/* Bot Text */}
              {msg.role === 'bot' && msg.type === 'text' && (
                <div className="bg-slate-800 border border-slate-700 text-slate-200 px-4 py-3 rounded-2xl rounded-tl-sm inline-block">
                  {msg.content}
                </div>
              )}

              {/* Bot Plan Card */}
              {msg.role === 'bot' && msg.type === 'plan' && (
                <PlanCard 
                  plan={msg.plan} 
                  isProcessing={isProcessing} 
                  onApprove={() => handleExecute(msg.ticketId, msg.plan)}
                  onModify={(feedback) => handleModifyPlan(msg.ticketId, msg.plan, feedback)}
                />
              )}

              {/* Bot Push Action Card */}
              {msg.role === 'bot' && msg.type === 'action' && (
                <div className="mt-2 w-full">
                  <div className="bg-slate-800 border border-slate-700 text-slate-200 p-4 rounded-xl shadow-lg mb-4">
                    <p className="mb-4 text-emerald-400 font-medium">{msg.content}</p>
                    <button 
                      onClick={() => handlePush(msg.ticketId)}
                      disabled={isProcessing}
                      className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                      <GitCommit size={16} />
                      Approve & Push to GitHub
                    </button>
                  </div>
                  
                  {/* Render the actual Code Diffs below the action box */}
                  {msg.fileDiffs && <DiffCard diffs={msg.fileDiffs} />}
                </div>
              )}
            </div>

            {/* User Avatar */}
            {msg.role === 'user' && (
              <div className="w-8 h-8 rounded-full bg-slate-700 flex items-center justify-center shrink-0 order-2">
                <User size={18} className="text-slate-300" />
              </div>
            )}
          </div>
        ))}
        <div ref={chatEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-slate-800 border-t border-slate-700">
        <form onSubmit={handleSend} className="relative flex items-center">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={isProcessing}
            placeholder="Enter Jira Ticket ID (e.g., KAN-123)..."
            className="w-full bg-slate-900 border border-slate-600 rounded-full pl-5 pr-14 py-3 text-white focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || isProcessing}
            className="absolute right-2 p-2 bg-blue-600 hover:bg-blue-500 rounded-full text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}