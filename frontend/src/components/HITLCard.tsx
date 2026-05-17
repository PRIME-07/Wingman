import { useState } from 'react';
import { useChatStore } from '../stores/useChatStore';
import { ShieldAlert, Check, X, Eye, MessageSquareQuote } from 'lucide-react';

interface HITLCardProps {
  onResume: (approved: boolean, feedback: string) => void;
}

export function HITLCard({ onResume }: HITLCardProps) {
  const { activeHITL } = useChatStore();
  const [feedback, setFeedback] = useState('');
  const [showDetails, setShowDetails] = useState(false);

  if (!activeHITL) return null;

  const handleAction = (approved: boolean) => {
    onResume(approved, feedback);
    setFeedback('');
    setShowDetails(false);
  };

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-in fade-in duration-200">
      <div className="bg-white dark:bg-mono-950 border-2 border-mono-900 dark:border-mono-700 rounded-xl shadow-2xl max-w-md w-full overflow-hidden animate-in zoom-in-95 duration-300 select-none">
        
        {/* Header Banner */}
        <div className="bg-mono-900 dark:bg-mono-800 text-white p-4 flex items-center gap-3">
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
          <div className="space-y-1.5">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider">Invoking Capability:</div>
            <div className="text-xs font-mono font-bold px-2 py-1 rounded bg-mono-50 dark:bg-mono-900 border border-mono-200 dark:border-mono-800 text-mono-700 dark:text-mono-300 break-all">
              {activeHITL.tool}
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider">Instruction Prompt:</div>
            <p className="text-sm text-mono-800 dark:text-mono-100 leading-relaxed border-l-2 border-mono-300 dark:border-mono-600 pl-3 font-medium italic">
              "{activeHITL.prompt}"
            </p>
          </div>

          {/* Collapsible Payload Inspector */}
          <div>
            <button 
              onClick={() => setShowDetails(!showDetails)}
              className="w-full py-1.5 flex items-center justify-between text-[10px] font-mono uppercase font-bold tracking-wider text-mono-500 hover:text-mono-900 dark:hover:text-white border-b border-dashed border-mono-200 dark:border-mono-800 mb-2 group"
            >
              <span className="flex items-center gap-1.5"><Eye size={12} className="group-hover:scale-110 transition-transform"/> VIEW PAYLOAD DATA</span>
              <span>{showDetails ? '[-]' : '[+]'}</span>
            </button>
            
            {showDetails && (
              <div className="max-h-48 overflow-y-auto p-2.5 rounded bg-mono-50 dark:bg-black/40 border border-mono-200/60 dark:border-mono-900 text-[10px] font-mono text-mono-600 dark:text-mono-400 animate-in slide-in-from-top-2">
                <pre className="whitespace-pre-wrap">
                  {JSON.stringify(activeHITL.data, null, 2)}
                </pre>
              </div>
            )}
          </div>

          {/* Instruction / Feedback Override */}
          <div className="space-y-1.5 pt-2 border-t border-mono-100 dark:border-mono-900">
            <div className="text-[10px] font-mono text-mono-400 uppercase tracking-wider flex items-center gap-1.5">
              <MessageSquareQuote size={12}/> Refine Instructions (Optional):
            </div>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Modify parameters, e.g., 'Change time to 3 PM'..."
              className="w-full p-2 text-xs font-mono bg-transparent border border-mono-200 dark:border-mono-800 focus:border-mono-400 dark:focus:border-mono-600 rounded-md focus:outline-none focus:ring-0 resize-none h-16 text-mono-800 dark:text-mono-200 placeholder-mono-400 dark:placeholder-mono-600"
            />
          </div>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => handleAction(false)}
              className="flex-1 py-2 flex items-center justify-center gap-2 rounded-md border border-mono-200 hover:bg-red-50 hover:text-red-600 dark:border-mono-800 dark:hover:bg-red-950/20 hover:border-red-200 dark:hover:border-red-900 font-mono font-bold text-[11px] uppercase transition-all active:scale-95"
            >
              <X size={14} />
              <span>Reject</span>
            </button>
            
            <button
              onClick={() => handleAction(true)}
              className="flex-1 py-2 flex items-center justify-center gap-2 rounded-md bg-mono-900 dark:bg-white text-white dark:text-mono-950 hover:bg-black dark:hover:bg-mono-100 font-mono font-bold text-[11px] uppercase transition-all active:scale-95 shadow-md"
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
