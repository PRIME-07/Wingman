import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore } from '../../stores/useChatStore';

export const TelemetryEmotionOverlay: React.FC = () => {
  const { telemetry, isStreaming } = useChatStore();
  
  if (!isStreaming || telemetry.length === 0) return null;
  
  const latest = telemetry[telemetry.length - 1];
  const label = latest.payload?.telemetry_label || latest.label || "Processing...";
  const priority = latest.payload?.priority || "ACTIVE";

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={label}
        initial={{ opacity: 0, x: -10 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: 10 }}
        className="flex flex-col justify-center"
      >
        <div className="flex items-center gap-2 pt-1.5">
          <span className="flex gap-1">
            <span className={`w-1 h-1 rounded-full animate-bounce ${priority === 'ACTIVE' ? 'bg-white' : 'bg-mono-400'}`} style={{ animationDelay: '0ms' }} />
            <span className={`w-1 h-1 rounded-full animate-bounce ${priority === 'ACTIVE' ? 'bg-white' : 'bg-mono-400'}`} style={{ animationDelay: '150ms' }} />
            <span className={`w-1 h-1 rounded-full animate-bounce ${priority === 'ACTIVE' ? 'bg-white' : 'bg-mono-400'}`} style={{ animationDelay: '300ms' }} />
          </span>
        </div>
        <div className="text-[10px] font-mono font-medium text-mono-400 dark:text-mono-500 mt-1 uppercase tracking-wider">
          {label}
        </div>
      </motion.div>
    </AnimatePresence>
  );
};
