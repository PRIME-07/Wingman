import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Bell, Calendar, X, Trash2, Activity, RotateCw } from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';

const getApiBaseUrl = () => {
  if (import.meta.env.VITE_API_URL) return import.meta.env.VITE_API_URL;
  if (import.meta.env.VITE_API_BASE_URL) return import.meta.env.VITE_API_BASE_URL;
  const BACKEND_HOST = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';
  const HTTP_PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${HTTP_PROTOCOL}//${BACKEND_HOST}/api/v1`;
};

const API_BASE_URL = getApiBaseUrl();

export function LiveActivitiesSidebar() {
  const { 
    setRightSidebarOpen,
    activeTimers,
    setActiveTimers,
    upcomingEvents,
    setUpcomingEvents,
    reminders,
    currentSessionId
  } = useChatStore();

  const [currentTime, setCurrentTime] = useState(new Date());
  const [syncTime, setSyncTime] = useState("T-00:00:00");
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Update clock and sync timer every second
  useEffect(() => {
    const timer = setInterval(() => {
      const now = new Date();
      setCurrentTime(now);
      
      // Calculate a pseudo-random "Neural Sync" countdown based on 15m intervals
      const intervalMs = 15 * 60 * 1000;
      const msSinceInterval = now.getTime() % intervalMs;
      const msLeft = intervalMs - msSinceInterval;
      
      const hours = Math.floor(msLeft / (60 * 60 * 1000));
      const mins = Math.floor((msLeft % (60 * 60 * 1000)) / (60 * 1000));
      const secs = Math.floor((msLeft % (60 * 1000)) / 1000);
      setSyncTime(`T-${hours.toString().padStart(2, '0')}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  // Poll for live activities
  const fetchLiveActivities = async () => {
    setIsRefreshing(true);
    try {
      // 1. Fetch Timers (scoped to currentSessionId to align with user's current session context)
      const timerRes = await fetch(`${API_BASE_URL}/tools/clock/timers?session_id=${currentSessionId || ''}`);
      if (timerRes.ok) {
        const data = await timerRes.json();
        setActiveTimers(data.active_timers || []);
      }

      // 2. Fetch Calendar Events
      const calendarRes = await fetch(`${API_BASE_URL}/calendar/upcoming?max_results=5`);
      if (calendarRes.ok) {
        const data = await calendarRes.json();
        setUpcomingEvents(data.events || []);
      }
    } catch (err) {
      console.error("Failed to fetch live activities:", err);
    } finally {
      // Small delay for visual feedback if refresh is too fast
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  useEffect(() => {
    fetchLiveActivities();
    
    // Refresh every 1 hour (3,600,000ms) to conserve API quota and billing costs
    const interval = setInterval(fetchLiveActivities, 3600000); 
    
    // Listen for proactive refresh triggers (e.g., from calendar tool executions)
    const handleRefreshTrigger = () => {
      console.log('[LiveActivities] Proactive calendar refresh triggered.');
      fetchLiveActivities();
    };
    
    window.addEventListener('refresh-calendar', handleRefreshTrigger);
    
    return () => {
      clearInterval(interval);
      window.removeEventListener('refresh-calendar', handleRefreshTrigger);
    };
  }, [currentSessionId]);

  const handleCancelTimer = async (timerId: string) => {
    try {
      const res = await fetch(`${API_BASE_URL}/tools/clock/timers/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ timer_id: timerId })
      });
      if (res.ok) {
        setActiveTimers(activeTimers.filter(t => t.timer_id !== timerId));
      }
    } catch (err) {
      console.error("Cancel timer failed:", err);
    }
  };

  return (
    <motion.aside 
      initial={{ width: 0 }}
      animate={{ width: 320 }}
      exit={{ width: 0 }}
      transition={{ type: 'spring', damping: 25, stiffness: 200 }}
      className="h-full border-l border-mono-100 dark:border-mono-900 bg-white/80 dark:bg-black/80 backdrop-blur-xl flex flex-col z-20 overflow-hidden flex-shrink-0"
    >
      <div className="w-80 h-full flex flex-col flex-shrink-0">
        {/* Header */}
        <div className="h-14 flex items-center justify-between px-6 border-b border-mono-100 dark:border-mono-900">
          <div className="flex items-center gap-2">
            <Activity size={14} className="text-mono-900 dark:text-white" />
            <h2 className="text-[10px] font-mono font-bold uppercase tracking-[0.2em] text-mono-900 dark:text-white">
              Live Activities
            </h2>
          </div>
          <button 
            onClick={() => setRightSidebarOpen(false)}
            className="p-1.5 rounded-full hover:bg-mono-100 dark:hover:bg-mono-900 text-mono-400 hover:text-mono-900 dark:hover:text-white transition-all"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-6">
          
          {/* Active Timers Section */}
          {activeTimers.length > 0 && (
            <section className="space-y-3">
              <div className="flex items-center justify-between px-2">
                <h3 className="text-[9px] font-mono font-bold text-mono-400 uppercase tracking-widest flex items-center gap-2">
                  <Clock size={10} /> Active Timers
                </h3>
                <span className="text-[8px] font-mono px-1.5 py-0.5 rounded bg-mono-100 dark:bg-mono-900 text-mono-600 dark:text-mono-400">
                  {activeTimers.length}
                </span>
              </div>
              
              <div className="space-y-2">
                <AnimatePresence mode="popLayout">
                  {activeTimers.map((timer) => (
                    <TimerItem key={timer.timer_id} timer={timer} onCancel={handleCancelTimer} />
                  ))}
                </AnimatePresence>
              </div>
            </section>
          )}

          {/* Reminders Section */}
          {reminders.length > 0 && (
            <section className="space-y-3">
              <h3 className="text-[9px] font-mono font-bold text-mono-400 uppercase tracking-widest flex items-center gap-2 px-2">
                <Bell size={10} /> Proactive Alerts
              </h3>
              <div className="space-y-2">
                <AnimatePresence mode="popLayout">
                  {reminders.map((rem, i) => (
                    <motion.div 
                      key={i} 
                      initial={{ opacity: 0, x: 20 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, scale: 0.95 }}
                      className="p-3 border border-blue-200/50 dark:border-blue-900/50 rounded-xl bg-blue-50/30 dark:bg-blue-900/10 flex items-center gap-3"
                    >
                      <div className="w-6 h-6 rounded-lg bg-blue-100 dark:bg-blue-900 flex items-center justify-center text-blue-600 dark:text-blue-400">
                        <Bell size={10} />
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-[10px] font-mono font-bold text-mono-900 dark:text-mono-100 truncate">{rem.label}</p>
                        <p className="text-[8px] font-mono text-mono-400">{rem.time}</p>
                      </div>
                    </motion.div>
                  ))}
                </AnimatePresence>
              </div>
            </section>
          )}

          {/* Upcoming Schedule Section */}
          <section className="space-y-3">
            <div className="flex items-center justify-between px-2">
              <h3 className="text-[9px] font-mono font-bold text-mono-400 uppercase tracking-widest flex items-center gap-2">
                <Calendar size={10} /> Daily Horizon
              </h3>
              <button 
                onClick={fetchLiveActivities}
                disabled={isRefreshing}
                className={`p-1 rounded-md hover:bg-mono-100 dark:hover:bg-mono-900 text-mono-400 hover:text-mono-900 dark:hover:text-white transition-all ${isRefreshing ? 'animate-spin opacity-50' : ''}`}
                title="Refresh Schedule"
              >
                <RotateCw size={10} />
              </button>
            </div>
            
            <div className="space-y-4">
              {(() => {
                const now = new Date();
                const tomorrow = new Date(now);
                tomorrow.setDate(now.getDate() + 1);
                
                const todayEvents = upcomingEvents.filter(e => {
        const dateStr = e.start?.dateTime || e.start?.date;
        if (!dateStr) return false;
        return new Date(dateStr).toDateString() === now.toDateString();
      });
                const tomorrowEvents = upcomingEvents.filter(e => {
                  const dateStr = e.start?.dateTime || e.start?.date;
                  if (!dateStr) return false;
                  return new Date(dateStr).toDateString() === tomorrow.toDateString();
                });

                if (todayEvents.length === 0 && tomorrowEvents.length === 0) {
                  return <p className="text-[9px] font-mono text-mono-400 italic px-2">Schedule clear for the next 48h</p>;
                }

                return (
                  <>
                    {todayEvents.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-[8px] font-mono font-bold text-mono-400 dark:text-mono-600 uppercase tracking-[0.2em] px-2 mb-1">Today</p>
                        {todayEvents.map((event, i) => (
                          <EventCard key={`today-${i}`} event={event} />
                        ))}
                      </div>
                    )}
                    
                    {tomorrowEvents.length > 0 && (
                      <div className="space-y-2 pt-2">
                        <p className="text-[8px] font-mono font-bold text-mono-400 dark:text-mono-600 uppercase tracking-[0.2em] px-2 mb-1">Upcoming</p>
                        {tomorrowEvents.map((event, i) => (
                          <EventCard key={`tmrw-${i}`} event={event} />
                        ))}
                      </div>
                    )}
                  </>
                );
              })()}
            </div>
          </section>

        </div>

        {/* Footer Info */}
        <div className="p-4 border-t border-mono-100 dark:border-mono-900 bg-mono-50/50 dark:bg-mono-950/50 space-y-3">
          <div className="flex items-center justify-between p-2 rounded-lg border border-mono-200 dark:border-mono-800 bg-white/50 dark:bg-black/50">
            <span className="text-[10px] font-mono text-mono-400">Sync:</span>
            <span className="text-[12px] font-mono font-bold text-mono-900 dark:text-white tracking-widest">{syncTime}</span>
          </div>
          <div className="flex items-center justify-between text-[8px] font-mono text-mono-400 uppercase tracking-tighter px-1">
            <span>System Status: Optimal</span>
            <span>{currentTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</span>
          </div>
        </div>
      </div>
    </motion.aside>
  );
}

function TimerItem({ timer, onCancel }: { timer: any, onCancel: (id: string) => void }) {
  const [timeLeft, setTimeLeft] = useState(timer.remaining_seconds);
  const [isCompleted, setIsCompleted] = useState(timer.remaining_seconds <= 0);

  // Sync state if props change (e.g. on live activities updates)
  useEffect(() => {
    setTimeLeft(timer.remaining_seconds);
    setIsCompleted(timer.remaining_seconds <= 0);
  }, [timer.remaining_seconds]);

  useEffect(() => {
    if (timeLeft <= 0) {
      if (!isCompleted) setIsCompleted(true);
      return;
    }
    const interval = setInterval(() => {
      setTimeLeft((prev: number) => Math.max(0, prev - 1));
    }, 1000);
    return () => clearInterval(interval);
  }, [timeLeft]);

  const duration = timer.duration_seconds || timer.total_seconds || 60;
  const progress = (timeLeft / duration) * 100;

  return (
    <motion.div 
      layout
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className={`p-6 border rounded-2xl shadow-xl overflow-hidden relative flex flex-col items-center justify-center gap-2 transition-colors duration-500 ${
        isCompleted 
          ? 'bg-green-500/10 border-green-500/30' 
          : 'bg-white dark:bg-[#050505] border-mono-100 dark:border-mono-900'
      }`}
    >
       {/* Background Progress Fill */}
       <div className="absolute bottom-0 left-0 w-full pointer-events-none opacity-[0.03] dark:opacity-[0.07]">
         <motion.div 
           initial={{ height: '0%' }}
           animate={{ height: `${100 - progress}%` }}
           className={`w-full ${isCompleted ? 'bg-green-500' : 'bg-mono-900 dark:bg-white'}`}
         />
       </div>

       <div className={`text-4xl font-mono font-black tracking-tighter ${isCompleted ? 'text-green-500' : 'text-mono-900 dark:text-white'}`}>
         {Math.floor(timeLeft / 60)}:{Math.floor(timeLeft % 60).toString().padStart(2, '0')}
       </div>
       
       <div className="text-center">
         <p className={`text-[11px] font-bold uppercase tracking-widest ${isCompleted ? 'text-green-400' : 'text-mono-900 dark:text-mono-100'}`}>
           {timer.label}
         </p>
         <p className="text-[8px] font-mono text-mono-400 mt-1 uppercase tracking-tighter">
           {isCompleted ? 'Finished' : 'Counting Down'}
         </p>
       </div>

       <button 
         onClick={() => onCancel(timer.timer_id)}
         className="absolute top-3 right-3 p-1.5 rounded-full hover:bg-mono-100 dark:hover:bg-mono-900 text-mono-300 hover:text-red-500 transition-colors"
       >
         <Trash2 size={12} />
       </button>
    </motion.div>
  );
}

function EventCard({ event }: { event: any }) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const dateStr = event.start?.dateTime || event.start?.date;
  const startTime = dateStr ? new Date(dateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : 'All Day';
  const endDateStr = event.end?.dateTime || event.end?.date;
  const endTime = endDateStr ? new Date(endDateStr).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : null;

  return (
    <div 
      onMouseEnter={() => setIsExpanded(true)}
      onMouseLeave={() => setIsExpanded(false)}
      className={`p-4 border rounded-2xl cursor-default transition-all duration-300 group ${
        isExpanded 
          ? 'bg-mono-50 dark:bg-mono-900/40 border-mono-300 dark:border-mono-700 shadow-xl' 
          : 'border-mono-100 dark:border-mono-900 hover:border-mono-200 dark:hover:border-mono-800 bg-transparent'
      }`}
    >
      <div className="space-y-1.5">
        <p className="text-[13px] font-bold text-mono-900 dark:text-mono-100 leading-tight">
          {event.summary}
        </p>
        <div className="flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-[#00FF00] shadow-[0_0_8px_rgba(0,255,0,0.6)] animate-pulse" />
          <p className="text-[11px] font-mono font-bold text-mono-500 dark:text-mono-400">
            {startTime}
          </p>
        </div>
      </div>

      <AnimatePresence>
        {isExpanded && endTime && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="pt-3 mt-3 border-t border-mono-200 dark:border-mono-800 flex items-center justify-between">
              <span className="text-[9px] font-mono uppercase text-mono-400">Ends At</span>
              <span className="text-[11px] font-mono font-bold text-mono-900 dark:text-mono-100">{endTime}</span>
            </div>
            {event.location && (
              <div className="pt-2">
                <p className="text-[8px] font-mono uppercase text-mono-400 mb-0.5">Location</p>
                <p className="text-[9px] text-mono-600 dark:text-mono-400 truncate">{event.location}</p>
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
