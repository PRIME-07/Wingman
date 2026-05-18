import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatPane, WelcomeView } from './components/ChatPane';
import { ChatInput } from './components/ChatInput';
import { HITLCard } from './components/HITLCard';
import { CalendarView } from './components/CalendarView';
import { AuthPrompt } from './components/AuthPrompt';
import { useChatStore } from './stores/useChatStore';
import { useWingmanConnection } from './hooks/useWingmanConnection';
import { LiveActivitiesSidebar } from './components/LiveActivitiesSidebar';
import { NotificationCenter } from './components/NotificationCenter';
import { Activity } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { ErrorBoundary } from './components/ErrorBoundary';

import { WingmanPatternBackground } from './components/background/WingmanPatternBackground';

function App() {
  const {
    setTheme,
    messages,
    isStreaming,
    currentSessionId,
    activeSidebarTab,
    wsConnected,
    fetchHistory,
    isRightSidebarOpen,
    setRightSidebarOpen,
    activeTimers
  } = useChatStore();

  // Hydration guard — starts true, blocks WelcomeView until fetchHistory completes.
  const [isHydrating, setIsHydrating] = useState(true);

  // Establish live persistent WS routing with back-end runtime
  const { sendMessage, respondHITL } = useWingmanConnection(currentSessionId);

  // Hydrate messages on initial mount
  useEffect(() => {
    if (currentSessionId) {
      fetchHistory(currentSessionId).finally(() => setIsHydrating(false));
    } else {
      setIsHydrating(false);
    }
  }, []);

  // Synchronize initial local storage theme prefs with visual DOM layers
  useEffect(() => {
    const savedTheme = localStorage.getItem('wingman-theme') as 'dark' | 'light' || 'dark';
    setTheme(savedTheme);
  }, [setTheme]);

  const isEmpty = !isHydrating && messages.length === 0;

  return (
    <ErrorBoundary>
      <div className="w-full h-screen flex bg-white dark:bg-[#000000] text-mono-800 dark:text-mono-200 transition-colors duration-200 overflow-hidden relative select-none">
      {/* 1. Left Navigation Pane */}
      <Sidebar />

      {/* 2. Main Content Shell (Center Workspace) */}
      <main className="flex-1 flex flex-col relative overflow-hidden bg-white dark:bg-[#000000]">
        <AnimatePresence>
          {isEmpty && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.8, ease: 'easeInOut' }}
              className="absolute inset-0 pointer-events-none z-0"
            >
              <WingmanPatternBackground />
            </motion.div>
          )}
        </AnimatePresence>

        {activeSidebarTab === 'timers' ? (
          <CalendarView />
        ) : (
          <>
            {/* Center Header Overlay */}
            <header className="h-14 flex items-center justify-between px-6 bg-transparent z-10 flex-shrink-0">
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                  <div className={`w-2 h-2 rounded-full animate-pulse ${wsConnected ? 'bg-[#00FF00] shadow-[0_0_10px_rgba(0,255,0,0.6)]' : 'bg-mono-600'}`} />
                  <span className="text-[8px] font-mono font-bold tracking-widest text-mono-900 dark:text-white uppercase px-1.5 py-0.5 rounded border border-mono-200/50 dark:border-mono-800">
                    {wsConnected ? 'Connected' : 'Disconnected'}
                  </span>
                </div>
              </div>
              
              <div className="flex items-center gap-4">
                {!isRightSidebarOpen && (
                  <button 
                    onClick={() => setRightSidebarOpen(true)}
                    className="p-2 rounded-lg border border-mono-200 dark:border-mono-800 text-mono-500 hover:text-mono-900 dark:hover:text-white transition-all flex items-center gap-2"
                    title="Toggle Live Activities"
                  >
                    <Activity size={14} />
                    <span className="text-[10px] font-mono font-bold uppercase tracking-tight">Live</span>
                  </button>
                )}
              </div>
            </header>

            {isEmpty ? (
              // 2.A: Empty State Center Canvas
              <motion.div 
                initial={{ opacity: 0, y: 15 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, ease: 'easeOut' }}
                className="flex-1 flex flex-col items-center justify-center px-6 pb-16 overflow-y-auto custom-scrollbar w-full relative z-10"
              >
                <WelcomeView />
                <div className="w-full max-w-3xl mt-6">
                  <ChatInput onSend={sendMessage} disabled={isStreaming} />
                </div>
              </motion.div>
            ) : (
              // 2.B: Conversation Thread Screen
              <div className="flex-1 flex flex-col relative overflow-hidden z-10">
                <ChatPane />

                {/* Bottom Input Anchor */}
                <div className="px-6 pb-6 pt-2 relative z-10">
                  <div className="absolute bottom-0 inset-x-0 h-32 bg-gradient-to-t from-white dark:from-black to-transparent pointer-events-none -z-10" />
                  <ChatInput
                    onSend={sendMessage}
                    disabled={isStreaming}
                  />
                </div>
              </div>
            )}
          </>
        )}
      </main>

      {/* 3. Right Activity Pane */}
      <AnimatePresence>
        {isRightSidebarOpen && <LiveActivitiesSidebar />}
      </AnimatePresence>

      {/* Dynamic Overlay Components */}
      <HITLCard onResume={respondHITL} />
      <AuthPrompt />
      
      {/* 4. Global Alerts Layer */}
      <NotificationCenter />

      </div>
    </ErrorBoundary>
  );
}

export default App;
