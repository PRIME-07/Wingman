import { useState, useEffect } from 'react';
import { useChatStore } from '../stores/useChatStore';
import { ShieldAlert, Check, X, Eye, MessageSquareQuote, Mail, Slack, Sparkles } from 'lucide-react';
import { motion } from 'framer-motion';

interface HITLCardProps {
  onResume: (approved: boolean, feedback: string, extra?: Record<string, any>) => void;
}

export function HITLCard({ onResume }: HITLCardProps) {
  const { activeHITL } = useChatStore();
  const [feedback, setFeedback] = useState('');
  const [showDetails, setShowDetails] = useState(false);

  // Editable Preview States
  const [recipient, setRecipient] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [channel, setChannel] = useState('');
  const [message, setMessage] = useState('');

  // Synchronize state values when activeHITL changes
  useEffect(() => {
    if (activeHITL) {
      setRecipient(activeHITL.data?.recipient || '');
      setSubject(activeHITL.data?.subject || '');
      setBody(activeHITL.data?.body || '');
      setChannel(activeHITL.data?.channel || '');
      setMessage(activeHITL.data?.message || '');
      setFeedback('');
    }
  }, [activeHITL]);

  if (!activeHITL) return null;

  const isSlack = activeHITL.tool === 'slack_draft';
  const isGmail = activeHITL.tool === 'gmail_draft';

  const handleAction = (approved: boolean) => {
    const extra: Record<string, any> = {};
    if (isSlack) {
      extra.channel = channel;
      extra.message = message;
    } else if (isGmail) {
      extra.recipient = recipient;
      extra.subject = subject;
      extra.body = body;
    }
    onResume(approved, feedback, extra);
    setFeedback('');
    setShowDetails(false);
  };

  const handleRefine = () => {
    const extra: Record<string, any> = { refine: true };
    if (isSlack) {
      extra.channel = channel;
      extra.message = message;
    } else if (isGmail) {
      extra.recipient = recipient;
      extra.subject = subject;
      extra.body = body;
    }
    onResume(false, feedback, extra);
    setFeedback('');
    setShowDetails(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className={`bg-white dark:bg-mono-950 border-2 border-mono-900 dark:border-mono-700 rounded-xl shadow-2xl w-full overflow-hidden animate-in zoom-in-95 duration-300 select-text ${
        isSlack || isGmail ? 'max-w-xl' : 'max-w-md'
      }`}>
        
        {/* Header Banner */}
        <div className="bg-mono-900 dark:bg-mono-800 text-white p-4 flex items-center gap-3 select-none">
          <div className="p-2 rounded-full bg-white/10">
            <ShieldAlert size={18} className="text-white animate-pulse" />
          </div>
          <div>
            <h3 className="text-xs font-mono font-bold uppercase tracking-widest">HITL Gateway Action</h3>
            <p className="text-[10px] text-mono-300 tracking-tight uppercase font-mono">Authorization requested for mutation</p>
          </div>
        </div>

        <div className="p-5 space-y-4">
          {/* Description */}
          <div className="space-y-1.5 select-none">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider">Invoking Capability:</div>
            <div className="text-xs font-mono font-bold px-2 py-1 rounded bg-mono-50 dark:bg-mono-900 border border-mono-200 dark:border-mono-800 text-mono-700 dark:text-mono-300 break-all">
              {activeHITL.tool}
            </div>
          </div>

          <div className="space-y-1.5 select-none">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider">Instruction Prompt:</div>
            <p className="text-sm text-mono-800 dark:text-mono-100 leading-relaxed border-l-2 border-mono-300 dark:border-mono-600 pl-3 font-medium italic font-sans">
              "{activeHITL.prompt}"
            </p>
          </div>

          {/* Slack Draft Preview */}
          {isSlack && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-2"
            >
              <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider flex items-center gap-1.5 select-none">
                <Slack size={12} className="text-[#E01E5A] dark:text-[#36C5F0]" /> Outbound Slack Message Preview (Editable):
              </div>
              <div className="rounded-lg border border-mono-200 dark:border-mono-800 bg-mono-50 dark:bg-black/20 overflow-hidden text-left font-sans shadow-inner">
                {/* Slack Header Mockup */}
                <div className="bg-[#4a154b] dark:bg-[#1f1a20] text-white px-3 py-1.5 flex items-center gap-2 text-[11px] font-bold border-b border-mono-200 dark:border-mono-800 select-none">
                  <Slack size={12} className="text-mono-300 animate-pulse" />
                  <span className="font-mono text-mono-300">#</span>
                  <input
                    type="text"
                    value={channel}
                    onChange={(e) => setChannel(e.target.value)}
                    className="bg-transparent border-none outline-none font-mono text-white tracking-tight focus:ring-0 w-full p-0 h-auto text-[11px] focus:outline-none"
                  />
                </div>
                
                {/* Slack Message Mockup */}
                <div className="p-3.5 flex gap-3">
                  {/* Avatar */}
                  <div className="w-8 h-8 rounded bg-[#36C5F0] text-white flex items-center justify-center font-bold text-xs shrink-0 select-none shadow-sm font-sans">
                    W
                  </div>
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-baseline gap-2 select-none font-sans">
                      <span className="font-bold text-xs text-mono-900 dark:text-mono-100">Wingman Agent</span>
                      <span className="text-[9px] text-mono-400 font-sans">Just now</span>
                      <span className="text-[9px] px-1 bg-mono-200 dark:bg-mono-800 text-mono-600 dark:text-mono-400 rounded uppercase font-mono font-bold tracking-wider">APP</span>
                    </div>
                    {/* Slack Body Textarea */}
                    <textarea
                      value={message}
                      onChange={(e) => setMessage(e.target.value)}
                      rows={5}
                      className="w-full text-xs text-mono-800 dark:text-mono-200 leading-relaxed bg-transparent border border-dashed border-mono-200 dark:border-mono-800 focus:border-mono-400 dark:focus:border-mono-600 focus:bg-white dark:focus:bg-mono-900/30 rounded-md focus:outline-none focus:ring-0 p-1.5 resize-y font-sans transition-all"
                    />
                  </div>
                </div>
              </div>
            </motion.div>
          )}

          {/* Gmail Draft Preview */}
          {isGmail && (
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="space-y-2"
            >
              <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider flex items-center gap-1.5 select-none">
                <Mail size={12} className="text-[#EA4335]" /> Outbound Email Draft Preview (Editable):
              </div>
              <div className="rounded-lg border border-mono-200 dark:border-mono-800 bg-mono-50 dark:bg-black/20 overflow-hidden text-left font-sans shadow-inner">
                {/* Email Header */}
                <div className="bg-mono-100 dark:bg-mono-950/40 p-3 space-y-2 border-b border-mono-200 dark:border-mono-900 text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-mono-400 font-mono text-[9px] uppercase w-12 shrink-0 select-none">To:</span>
                    <input
                      type="text"
                      value={recipient}
                      onChange={(e) => setRecipient(e.target.value)}
                      className="w-full px-2 py-0.5 rounded bg-white dark:bg-mono-900 border border-mono-200 dark:border-mono-800 text-[11px] font-sans font-medium text-mono-800 dark:text-mono-200 focus:outline-none focus:border-mono-400 dark:focus:border-mono-600"
                    />
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-mono-400 font-mono text-[9px] uppercase w-12 shrink-0 select-none">Subject:</span>
                    <input
                      type="text"
                      value={subject}
                      onChange={(e) => setSubject(e.target.value)}
                      className="w-full px-2 py-0.5 rounded bg-white dark:bg-mono-900 border border-mono-200 dark:border-mono-800 text-[11px] font-sans font-semibold text-mono-850 dark:text-mono-100 focus:outline-none focus:border-mono-400 dark:focus:border-mono-600"
                    />
                  </div>
                </div>
                
                {/* Email Body */}
                <textarea
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={6}
                  className="w-full p-4 bg-white dark:bg-mono-950 text-xs text-mono-800 dark:text-mono-200 leading-relaxed font-sans resize-y focus:outline-none focus:ring-0 border-none border-t border-mono-200 dark:border-mono-900"
                />
              </div>
            </motion.div>
          )}

          {/* Collapsible Payload Inspector */}
          <div>
            <button 
              onClick={() => setShowDetails(!showDetails)}
              className="w-full py-1.5 flex items-center justify-between text-[10px] font-mono uppercase font-bold tracking-wider text-mono-500 hover:text-mono-900 dark:hover:text-white border-b border-dashed border-mono-200 dark:border-mono-800 mb-2 group select-none"
            >
              <span className="flex items-center gap-1.5"><Eye size={12} className="group-hover:scale-110 transition-transform"/> VIEW PAYLOAD DATA</span>
              <span>{showDetails ? '[-]' : '[+]'}</span>
            </button>
            
            {showDetails && (
              <div className="max-h-48 overflow-y-auto p-2.5 rounded bg-mono-50 dark:bg-black/40 border border-mono-200/60 dark:border-mono-900 text-[10px] font-mono text-mono-600 dark:text-mono-400 animate-in slide-in-from-top-2 select-text">
                <pre className="whitespace-pre-wrap">
                  {JSON.stringify(activeHITL.data, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Instruction / Feedback Override */}
          <div className="space-y-1.5 pt-2 border-t border-mono-100 dark:border-mono-900">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider flex items-center gap-1.5 select-none">
              <MessageSquareQuote size={12}/> Refine Instructions / Suggest Revisions:
            </div>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="e.g., 'Change recipient to info@...', 'Make it sound more urgent'..."
              className="w-full p-2 text-xs font-mono bg-transparent border border-mono-200 dark:border-mono-800 focus:border-mono-400 dark:focus:border-mono-600 rounded-md focus:outline-none focus:ring-0 resize-none h-16 text-mono-800 dark:text-mono-200 placeholder-mono-400 dark:placeholder-mono-600 font-mono"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2 select-none">
            <button
              onClick={() => handleAction(false)}
              className="flex-1 py-2 flex items-center justify-center gap-1.5 rounded-md border border-mono-200 hover:bg-red-50 hover:text-red-600 dark:border-mono-800 dark:hover:bg-red-950/20 hover:border-red-200 dark:hover:border-red-900 font-mono font-bold text-[11px] uppercase transition-all active:scale-95 text-mono-650 dark:text-mono-300"
            >
              <X size={14} />
              <span>Reject</span>
            </button>

            <button
              onClick={() => handleRefine()}
              disabled={!feedback.trim()}
              className="flex-1 py-2 flex items-center justify-center gap-1.5 rounded-md border border-mono-200 hover:bg-blue-50 hover:text-blue-600 dark:border-mono-800 dark:hover:bg-blue-950/20 hover:border-blue-200 dark:hover:border-blue-900 font-mono font-bold text-[11px] uppercase transition-all active:scale-95 disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-inherit disabled:cursor-not-allowed text-mono-650 dark:text-mono-300"
            >
              <Sparkles size={14} />
              <span>Refine</span>
            </button>
            
            <button
              onClick={() => handleAction(true)}
              className="flex-1 py-2 flex items-center justify-center gap-1.5 rounded-md bg-mono-900 dark:bg-white text-white dark:text-mono-950 hover:bg-black dark:hover:bg-mono-100 font-mono font-bold text-[11px] uppercase transition-all active:scale-95 shadow-md"
            >
              <Check size={14} />
              <span>Approve</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
