import { useRef, useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useChatStore } from '../stores/useChatStore';
import { motion } from 'framer-motion';
import { Mascot } from '../emotion/components/Mascot';
import { MascotRenderer } from '../emotion/components/MascotRenderer';
import { TelemetryEmotionOverlay } from '../emotion/components/TelemetryEmotionOverlay';
import { emotionEngine } from '../emotion/engine';
import { WingmanEmotion, ALL_EMOTIONS } from '../emotion/emotion-map';

// Known expression tag mappings mapped precisely to source file name casings
const KNOWN_EXPRESSIONS = ALL_EMOTIONS;

/**
 * High-fidelity real-time stream parser. Intercepts expression tags 
 * at the beginning of assistant messages, and masks them from rendering 
 * in the chat bubble while streaming.
 */
function parseMessageExpression(rawContent: string): { expression: string; cleanContent: string } {
  if (!rawContent) return { expression: "happy", cleanContent: "" };

  let cleanContent = rawContent;
  let expression: WingmanEmotion = "happy";

  // 1. Process all completed expression tags in the message (supporting both [] and () braces and multi-word tags)
  const expressionRegex = /[\(\[]EXPRESSION:\s*([^\)\]]+)[\)\]]/gi;
  let match;
  let lastFoundExpr: string | null = null;

  while ((match = expressionRegex.exec(rawContent)) !== null) {
    lastFoundExpr = match[1];
  }

  if (lastFoundExpr) {
    const expr = lastFoundExpr.trim().toLowerCase();
    const normalizedExpr = expr === 'neutral' ? 'happy' : expr;
    const found = (KNOWN_EXPRESSIONS.find(k => k.toLowerCase() === normalizedExpr) || "happy") as WingmanEmotion;
    expression = found === "excited" ? "happy" : found;

    // Side effect: update engine with the latest parsed emotion
    emotionEngine.transition(expression);
  }

  // Strip all completed expression tags from the clean content
  cleanContent = cleanContent.replace(/[\(\[]EXPRESSION:\s*[^\)\]]+[\)\]]\s*/gi, '');

  // 2. Handle partial/streaming tags at the end of the text to mask them while they are typing
  const trimmed = cleanContent.trimEnd();
  const lastBracketIndex = Math.max(trimmed.lastIndexOf('['), trimmed.lastIndexOf('('));

  if (lastBracketIndex !== -1) {
    const tagContent = trimmed.substring(lastBracketIndex);
    // Regex matching any valid prefix of "[EXPRESSION: <letters>" or "(EXPRESSION: <letters>"
    const partialMatchRegex = /^[\(\[](?:E(?:X(?:P(?:R(?:E(?:S(?:S(?:I(?:O(?:N(?::(?:\s*[a-zA-Z\s]*)?)?)?)?)?)?)?)?)?)?)?)?$/i;

    if (partialMatchRegex.test(tagContent) || tagContent.toLowerCase().startsWith('[expression') || tagContent.toLowerCase().startsWith('(expression')) {
      const emotionMatch = tagContent.match(/[\(\[]EXPRESSION:\s*([a-zA-Z\s]*)/i);
      const emotionalPrefix = emotionMatch ? emotionMatch[1] : "";
      const parsed = (KNOWN_EXPRESSIONS.find(k => k.toLowerCase().startsWith(emotionalPrefix.toLowerCase())) || "thinking") as WingmanEmotion;
      const found = parsed === "proud" ? "happy" : parsed;

      // Side effect: update engine with transient state
      emotionEngine.transition(found === "excited" ? "happy" : found);

      // Mask the partial tag completely
      cleanContent = cleanContent.substring(0, lastBracketIndex);
    }
  }

  return {
    expression,
    cleanContent
  };
}

export function ChatPane() {
  const { messages, isStreaming, telemetry } = useChatStore();
  const bottomRef = useRef<HTMLDivElement>(null);

  // Smooth scroll lock to follow real-time token feeds
  useEffect(() => {
    if (isStreaming) {
      bottomRef.current?.scrollIntoView({ behavior: 'auto' });
    } else {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, isStreaming]);

  if (messages.length === 0) {
    return null;
  }

  const lastMsg = messages[messages.length - 1];
  // Dynamically suppress telemetry card when response text begins streaming to prevent it from being pushed down
  const isResponseStarted = lastMsg &&
    lastMsg.role === 'assistant' &&
    parseMessageExpression(lastMsg.content).cleanContent.trim().length > 0;

  return (
    <div className="flex-1 overflow-y-auto px-4 md:px-8 py-6 space-y-6 select-text relative custom-scrollbar">
      {messages.map((msg, idx) => (
        <MessageBubble
          key={msg.id || idx}
          message={msg}
          isLast={idx === messages.length - 1}
          isStreaming={isStreaming}
        />
      ))}

      {/* Abstract Telemetry Streaming Status (Claude-like) */}
      {isStreaming && telemetry.length > 0 && !isResponseStarted && (
        <AbstractTelemetryStatus />
      )}

      <div ref={bottomRef} className="h-12" />
    </div>
  );
}

function AbstractTelemetryStatus() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className="flex gap-4 md:gap-6 max-w-3xl mx-auto justify-start w-full"
    >
      <div className="w-9 h-9 rounded-lg bg-mono-50 dark:bg-mono-950 flex items-center justify-center shrink-0 shadow-sm border border-mono-200/60 dark:border-mono-800/80 mt-0.5 overflow-hidden">
        <Mascot size="md" />
      </div>
      <TelemetryEmotionOverlay />
    </motion.div>
  );
}

interface WelcomePhrase {
  phrase: string;
  emotions: WingmanEmotion[];
}

const WELCOME_PHRASES: WelcomePhrase[] = [
  {
    phrase: "Yooo, you’re back what’s happening today?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "Okayyy what’s the vibe today?",
    emotions: ["happy", "excited"]
  },
  {
    phrase: "Good to see you again what’s on your mind?",
    emotions: ["happy", "thankful"]
  },
  {
    phrase: "Alright, tell me everything. what are we getting into today?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "I’m hereee. what do you need help with?",
    emotions: ["thankful", "shy"]
  },
  {
    phrase: "Soo… what’s today looking like?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "What are we overthinking together today ",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "Okay wait, I’m curious now what’s up?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "Always nice seeing you pop in ",
    emotions: ["thankful", "shy"]
  },
  {
    phrase: "What’s the move today?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "I got you, what do you need?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "We being productive today or just surviving?",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "Alright I’m locked in. what’s going on?",
    emotions: ["happy", "excited"]
  },
  {
    phrase: "Brain dump time. hit me with whatever’s on your mind.",
    emotions: ["thankful", "happy"]
  },
  {
    phrase: "Okay but first — how’s your day going?",
    emotions: ["happy", "thankful"]
  },
  {
    phrase: "You bring the chaos, I’ll help sort it out ",
    emotions: ["excited", "happy"]
  },
  {
    phrase: "Lowkey missed our conversations what’s up?",
    emotions: ["inLove", "glad"]
  },
  {
    phrase: "What are we figuring out today?",
    emotions: ["happy", "excited"]
  },
  {
    phrase: "I’m all ears ",
    emotions: ["thankful", "happy"]
  },
  {
    phrase: "Alrighttt, where do we start?",
    emotions: ["excited", "happy"]
  }
];

// Minimalist premium welcome card utilizing the new Mascot system
export function WelcomeView() {
  const { currentSessionId } = useChatStore();
  const [welcomeData, setWelcomeData] = useState<{ phrase: string; emotions: WingmanEmotion[] }>(() => {
    const randomPhrase = WELCOME_PHRASES[Math.floor(Math.random() * WELCOME_PHRASES.length)];
    return { phrase: randomPhrase.phrase, emotions: randomPhrase.emotions };
  });
  const emotionIndexRef = useRef<number>(0);

  // Reset phrase and initial emotion transition on session change
  useEffect(() => {
    const randomPhrase = WELCOME_PHRASES[Math.floor(Math.random() * WELCOME_PHRASES.length)];
    setWelcomeData({
      phrase: randomPhrase.phrase,
      emotions: randomPhrase.emotions
    });
    emotionIndexRef.current = 0;
    emotionEngine.transition(randomPhrase.emotions[0], true);
  }, [currentSessionId]);

  // 2. Setup cycling loop for emotions every 5 seconds
  useEffect(() => {
    if (!welcomeData || welcomeData.emotions.length <= 1) return;

    const interval = setInterval(() => {
      emotionIndexRef.current = (emotionIndexRef.current + 1) % welcomeData.emotions.length;
      const nextEmotion = welcomeData.emotions[emotionIndexRef.current];

      // Dynamic animation transition via emotion engine subscription
      emotionEngine.transition(nextEmotion, true);
    }, 5000);

    return () => clearInterval(interval);
  }, [welcomeData]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.6, ease: 'easeOut' }}
      className="flex flex-col items-center justify-center p-6 text-center w-full max-w-3xl relative z-10"
    >
      {/* Mascot container with premium soft glow backing bounded to content size */}
      <div className="relative mb-6 w-fit mx-auto">
        <div className="absolute inset-0 bg-mono-100 dark:bg-white/5 rounded-full blur-3xl scale-150 opacity-20 animate-pulse-slow avatar-glow" />
        <Mascot size="hero" enableTelemetry={false} />
      </div>

      <h2 className="text-2xl sm:text-3xl font-medium tracking-tight text-mono-900 dark:text-white mb-1 font-sans">
        {welcomeData.phrase}
      </h2>
    </motion.div>
  );
}

// Message visualization with dynamic emotion parsing and markdown rendering
function MessageBubble({ message, isLast, isStreaming }: { message: { role: string; content: string }, isLast?: boolean, isStreaming?: boolean }) {
  const isUser = message.role === 'user';

  // Parse expression and payload
  let { expression, cleanContent } = isUser
    ? { expression: "happy", cleanContent: message.content }
    : parseMessageExpression(message.content);

  // Render empty initial assistant messages gracefully
  if (!isUser && !message.content) return null;
  if (!isUser && !cleanContent && message.content.startsWith('[')) return null; // Hide typing tag stage

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-4 md:gap-6 max-w-3xl mx-auto w-full ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div className="w-9 h-9 rounded-lg bg-mono-50 dark:bg-mono-950 flex items-center justify-center shrink-0 shadow-sm border border-mono-200/60 dark:border-mono-800/80 mt-0.5 overflow-hidden">
          <MascotRenderer emotion={expression as WingmanEmotion} size="md" />
        </div>
      )}

      <div className={`flex-1 max-w-[85%] px-4 py-3.5 rounded-2xl transition-all duration-200 ${isUser
        ? 'bg-mono-100 dark:bg-mono-900 text-mono-900 dark:text-mono-100 rounded-tr-none font-mono text-xs leading-relaxed border border-mono-200/60 dark:border-mono-800'
        : 'bg-transparent text-mono-800 dark:text-mono-200'
        }`}>
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className={`prose dark:prose-invert prose-sm max-w-none prose-pre:bg-mono-50 dark:prose-pre:bg-mono-950 prose-pre:border prose-pre:border-mono-200 dark:prose-pre:border-mono-900 prose-pre:text-mono-800 dark:prose-pre:text-mono-300 prose-code:text-mono-800 dark:prose-code:text-mono-200 prose-a:text-mono-600 dark:prose-a:text-mono-400 ${(!isUser && isLast && isStreaming) ? 'streaming-cursor' : ''}`}>
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Custom high-fidelity code block renderer
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '');
                  return !inline ? (
                    <div className="relative group mt-2 mb-4">
                      <div className="absolute top-2 right-3 text-[10px] font-mono uppercase tracking-widest text-mono-400 opacity-0 group-hover:opacity-100 transition-opacity select-none">
                        {match ? match[1] : 'code'}
                      </div>
                      <pre className="overflow-x-auto font-mono p-4 rounded-lg text-xs leading-relaxed bg-mono-50 dark:bg-black/40 border border-mono-200 dark:border-mono-900">
                        <code className={className} {...props}>
                          {children}
                        </code>
                      </pre>
                    </div>
                  ) : (
                    <code className="px-1.5 py-0.5 rounded bg-mono-100 dark:bg-mono-900 font-mono text-[11px] text-mono-900 dark:text-mono-200 border border-mono-200/50 dark:border-mono-800" {...props}>
                      {children}
                    </code>
                  );
                },
                // Customize link behaviors to force open in new tab securely
                a: ({ node, ...props }: any) => (
                  <a {...props} target="_blank" rel="noopener noreferrer" />
                ),
                // Customize table layouts
                table: ({ children }) => (
                  <div className="overflow-x-auto my-4 border border-mono-200 dark:border-mono-900 rounded-lg">
                    <table className="min-w-full divide-y divide-mono-200 dark:divide-mono-900 font-mono text-xs">{children}</table>
                  </div>
                ),
                th: ({ children }) => (
                  <th className="px-3 py-2 bg-mono-50 dark:bg-mono-950 text-left font-bold uppercase tracking-wider text-mono-700 dark:text-mono-300">{children}</th>
                ),
                td: ({ children }) => (
                  <td className="px-3 py-2 text-mono-600 dark:text-mono-400 border-t border-mono-200 dark:border-mono-900">{children}</td>
                )
              }}
            >
              {cleanContent}
            </ReactMarkdown>
          </div>
        )}
      </div>
    </motion.div>
  );
}
