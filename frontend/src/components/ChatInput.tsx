import React, { useState, useRef, useEffect } from 'react';
import { Send, ChevronDown, Sparkles, Zap, Image, X } from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';
import type { ModelTier, ReasoningEffort } from '../types';

interface ChatInputProps {
  onSend: (message: string, image?: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState('');
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const { currentModel, setModel, currentReasoningEffort, setReasoningEffort } = useChatStore();
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };
  
  // Dropdown visibility tracking and click containment refs
  const [isModelOpen, setIsModelOpen] = useState(false);
  const [isPriorityOpen, setIsPriorityOpen] = useState(false);
  const modelRef = useRef<HTMLDivElement>(null);
  const priorityRef = useRef<HTMLDivElement>(null);

  // Premium Click-Outside handler to auto-dim dropdown elements
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const targetNode = event.target as Node;
      if (modelRef.current && !modelRef.current.contains(targetNode)) {
        setIsModelOpen(false);
      }
      if (priorityRef.current && !priorityRef.current.contains(targetNode)) {
        setIsPriorityOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Auto-resize textarea height to match content dynamically
  useEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.min(textarea.scrollHeight, 220)}px`;
  }, [text]);

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!text.trim() || disabled) return;
    onSend(text.trim(), imagePreview || undefined);
    setText('');
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const items = e.clipboardData?.items;
    if (!items) return;

    for (let i = 0; i < items.length; i++) {
      const item = items[i];
      if (item.type.indexOf('image') !== -1) {
        const file = item.getAsFile();
        if (file) {
          e.preventDefault(); // Prevent standard pasting of image files as text
          const reader = new FileReader();
          reader.onloadend = () => {
            setImagePreview(reader.result as string);
          };
          reader.readAsDataURL(file);
          break; // Stop looking after finding the first image
        }
      }
    }
  };

  return (
    <form 
      onSubmit={handleSubmit} 
      className="relative w-full bg-white dark:bg-[#000000] border border-mono-200/80 dark:border-mono-800 rounded-2xl shadow-[0_8px_32px_rgba(0,0,0,0.04)] dark:shadow-[0_12px_48px_rgba(0,0,0,0.6)] focus-within:border-mono-400 dark:focus-within:border-mono-600 transition-all duration-300 flex flex-col"
    >
      {/* Hidden file input for direct image attachments */}
      <input 
        type="file" 
        accept="image/*" 
        ref={fileInputRef} 
        className="hidden" 
        onChange={handleImageChange} 
      />

      {/* Dynamic Image Preview Canvas on top of the chat area */}
      {imagePreview && (
        <div className="px-5 pt-4 flex items-center gap-2">
          <div className="relative w-14 h-14 rounded-lg overflow-hidden border border-mono-200/80 dark:border-mono-800 bg-mono-100 dark:bg-mono-950 group shadow-sm flex-shrink-0 animate-in fade-in zoom-in-95 duration-200">
            <img src={imagePreview} alt="Upload preview" className="w-full h-full object-cover" />
            
            {/* Dimming backdrop overlay that triggers on group hover */}
            <div className="absolute inset-0 bg-black/25 opacity-0 group-hover:opacity-100 transition-opacity duration-150 pointer-events-none" />

            {/* Hover-dismiss button */}
            <button
              type="button"
              onClick={() => {
                setImagePreview(null);
                if (fileInputRef.current) fileInputRef.current.value = '';
              }}
              className="absolute top-1 right-1 p-0.5 rounded-full bg-black/75 hover:bg-black text-white opacity-0 group-hover:opacity-100 transition-all duration-150 shadow active:scale-90"
            >
              <X size={10} />
            </button>
          </div>
        </div>
      )}
      {/* Central Large Area: Text Input */}
      <div className="px-5 pt-4 pb-2">
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          disabled={disabled}
          rows={1}
          placeholder="Ask anything..."
          className="w-full bg-transparent border-none text-mono-900 dark:text-mono-100 placeholder-mono-400 dark:placeholder-mono-600 focus:outline-none focus:ring-0 text-[15px] leading-relaxed py-1.5 resize-none font-sans min-h-[44px] overflow-y-auto"
          style={{ scrollbarWidth: 'none' }}
        />
      </div>

      {/* Bottom Action / Dropdown Row */}
      <div className="px-4 pb-3 pt-1 flex items-center justify-between border-t border-transparent">
        
        {/* Left side: Configuration Pills */}
        <div className="flex items-center gap-1.5">
          {/* Model Select */}
          <div ref={modelRef} className="relative">
            <button 
              type="button"
              onClick={() => {
                setIsModelOpen(!isModelOpen);
                setIsPriorityOpen(false); // Mutual exclusion for clean UI
              }}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-transparent hover:bg-mono-100/50 dark:hover:bg-mono-900/40 text-[11px] font-medium transition-all duration-150 select-none ${
                isModelOpen 
                  ? 'bg-mono-50 dark:bg-mono-900/50 text-mono-900 dark:text-white' 
                  : 'text-mono-600 dark:text-mono-400 hover:text-mono-900 dark:hover:text-white'
              }`}
            >
              <Sparkles size={11} className="text-mono-400" />
              <span>{currentModel}</span>
              <ChevronDown size={11} className={`opacity-60 transition-transform duration-200 ${isModelOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Floating Dropdown */}
            {isModelOpen && (
              <div className="absolute top-full left-0 mt-1.5 flex flex-col bg-white dark:bg-[#0c0c0c] border border-mono-200 dark:border-mono-800 rounded-xl shadow-2xl overflow-hidden min-w-[150px] z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="px-3 py-2 border-b border-mono-100 dark:border-mono-900 text-[9px] font-mono uppercase tracking-wider text-mono-400">Model Engine</div>
                {(['GPT-5.4-mini'] as ModelTier[]).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => {
                      setModel(m);
                      setIsModelOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2.5 text-xs font-medium transition-colors ${
                      currentModel === m 
                        ? 'bg-mono-50 dark:bg-mono-900 text-mono-900 dark:text-white' 
                        : 'text-mono-600 dark:text-mono-400 hover:bg-mono-50 dark:hover:bg-mono-900/50 hover:text-mono-900 dark:hover:text-white'
                    }`}
                  >
                    {m}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Priority Select */}
          <div ref={priorityRef} className="relative">
            <button 
              type="button"
              onClick={() => {
                setIsPriorityOpen(!isPriorityOpen);
                setIsModelOpen(false); // Mutual exclusion for clean UI
              }}
              className={`flex items-center gap-1 px-2.5 py-1.5 rounded-lg border border-transparent hover:bg-mono-100/50 dark:hover:bg-mono-900/40 text-[11px] font-medium transition-all duration-150 select-none ${
                isPriorityOpen 
                  ? 'bg-mono-50 dark:bg-mono-900/50 text-mono-900 dark:text-white' 
                  : 'text-mono-600 dark:text-mono-400 hover:text-mono-900 dark:hover:text-white'
              }`}
            >
              <Zap size={11} className="text-mono-400" />
              <span>{currentReasoningEffort}</span>
              <ChevronDown size={11} className={`opacity-60 transition-transform duration-200 ${isPriorityOpen ? 'rotate-180' : ''}`} />
            </button>
            
            {/* Floating Dropdown */}
            {isPriorityOpen && (
              <div className="absolute top-full left-0 mt-1.5 flex flex-col bg-white dark:bg-[#0c0c0c] border border-mono-200 dark:border-mono-800 rounded-xl shadow-2xl overflow-hidden min-w-[130px] z-50 animate-in fade-in slide-in-from-top-2 duration-200">
                <div className="px-3 py-2 border-b border-mono-100 dark:border-mono-900 text-[9px] font-mono uppercase tracking-wider text-mono-400">Reasoning Effort</div>
                {(['Low', 'Medium', 'High'] as ReasoningEffort[]).map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => {
                      setReasoningEffort(p);
                      setIsPriorityOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2.5 text-xs font-medium transition-colors ${
                      currentReasoningEffort === p 
                        ? 'bg-mono-50 dark:bg-mono-900 text-mono-900 dark:text-white' 
                        : 'text-mono-600 dark:text-mono-400 hover:bg-mono-50 dark:hover:bg-mono-900/50 hover:text-mono-900 dark:hover:text-white'
                    }`}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right side: Utilities & Submit */}
        <div className="flex items-center gap-2">
          {/* Image Context Upload Shortcut Trigger */}
          <button
            type="button"
            title="Attach image context"
            onClick={() => fileInputRef.current?.click()}
            className="w-8 h-8 flex items-center justify-center rounded-full border border-transparent hover:border-mono-200 dark:hover:border-mono-800 text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900/50 transition-all"
          >
            <Image size={15} />
          </button>

          {/* Ultra clean round Send button */}
          <button
            type="submit"
            disabled={disabled || !text.trim()}
            className={`w-8 h-8 flex items-center justify-center rounded-full transition-all duration-200 ${
              disabled || !text.trim()
                ? 'bg-mono-100 dark:bg-mono-900 text-mono-300 dark:text-mono-700 cursor-not-allowed'
                : 'bg-mono-900 dark:bg-white text-white dark:text-mono-950 shadow active:scale-90 hover:bg-black dark:hover:bg-mono-100'
            }`}
          >
            <Send size={14} />
          </button>
        </div>
      </div>
    </form>
  );
}
