import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Bell, Clock, Calendar } from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';

export const NotificationCenter: React.FC = () => {
  const { notifications, removeNotification } = useChatStore();

  return (
    <div className="fixed top-8 left-1/2 -translate-x-1/2 z-[9999] flex flex-col gap-4 pointer-events-none items-center">
      <AnimatePresence>
        {notifications.map((n) => (
          <motion.div
            key={n.id}
            initial={{ opacity: 0, y: -40, scale: 0.9 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9, transition: { duration: 0.2 } }}
            className="
              pointer-events-auto w-[420px] p-5 rounded-2xl border-2 
              bg-[#050505]/90 border-green-500/40 shadow-[0_0_50px_rgba(34,197,94,0.15)]
              backdrop-blur-3xl flex gap-4 relative overflow-hidden
            "
          >
            {/* Pulsing Green Glow */}
            <motion.div 
              animate={{ opacity: [0.1, 0.3, 0.1] }}
              transition={{ duration: 3, repeat: Infinity }}
              className="absolute inset-0 bg-green-500/[0.03]" 
            />

            <div className="w-12 h-12 rounded-xl bg-green-500/10 border border-green-500/20 flex items-center justify-center shrink-0 text-green-400">
              {n.type === 'timer' ? <Clock size={24} /> : 
               n.type === 'calendar' ? <Calendar size={24} /> : <Bell size={24} />}
            </div>

            <div className="flex-1 min-w-0 pr-6">
              <h4 className="text-white font-black text-sm uppercase tracking-widest flex items-center gap-2">
                <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
                {n.title}
              </h4>
              <p className="text-mono-300 text-xs font-medium leading-relaxed mt-1.5">
                {n.message}
              </p>
            </div>

            <button
              onClick={() => removeNotification(n.id)}
              className="absolute top-4 right-4 text-mono-500 hover:text-white transition-colors p-1 hover:bg-white/5 rounded-lg"
            >
              <X size={16} />
            </button>

            {/* Visual countdown progress bar (30 seconds) */}
            <div className="absolute bottom-0 left-0 h-1 bg-white/5 w-full overflow-hidden">
               <motion.div 
                 initial={{ width: '100%' }}
                 animate={{ width: '0%' }}
                 transition={{ duration: 30, ease: 'linear' }}
                 onAnimationComplete={() => removeNotification(n.id)}
                 className="h-full bg-green-500"
               />
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
};
