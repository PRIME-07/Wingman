import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon, 
  Clock, 
  Loader2, 
  AlertCircle, 
  X, 
  Trash2, 
  Plus, 
  MapPin, 
  AlignLeft, 
  Save 
} from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';

const BACKEND_HOST = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';
const HTTP_PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
const API_BASE_URL = `${HTTP_PROTOCOL}//${BACKEND_HOST}/api/v1`;

interface CalendarEvent {
  id: string;
  summary: string;
  description?: string;
  location?: string;
  start: {
    dateTime?: string;
    date?: string;
  };
  end: {
    dateTime?: string;
    date?: string;
  };
}

export function CalendarView() {
  const { addTelemetry } = useChatStore();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [events, setEvents] = useState<CalendarEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);

  // 1. Format month/year label
  const currentYear = currentDate.getFullYear();
  const monthName = currentDate.toLocaleString('default', { month: 'long' });

  // 2. Date parsing boundaries
  const getMonthBoundaries = (date: Date) => {
    const start = new Date(date.getFullYear(), date.getMonth(), 1, 0, 0, 0);
    const end = new Date(date.getFullYear(), date.getMonth() + 1, 0, 23, 59, 59);
    return { start, end };
  };

  // 3. Data Hydration Function
  const fetchMonthEvents = async () => {
    const { start, end } = getMonthBoundaries(currentDate);
    
    // Pad boundaries slightly to account for overlapping edge cells in UI grid
    const padStart = new Date(start);
    padStart.setDate(padStart.getDate() - 7);
    const padEnd = new Date(end);
    padEnd.setDate(padEnd.getDate() + 7);

    try {
      setIsLoading(true);
      setError(null);

      const res = await fetch(
        `${API_BASE_URL}/calendar/events?start=${encodeURIComponent(padStart.toISOString())}&end=${encodeURIComponent(padEnd.toISOString())}`
      );

      if (!res.ok) {
        if (res.status === 401) {
          throw new Error("Link account to sync active logs.");
        }
        throw new Error("Failed to communicate with temporal matrix.");
      }

      const data = await res.json();
      setEvents(data);
      
      addTelemetry({
        type: 'info',
        label: 'Calendar Sync',
        message: `Synced ${data.length} checkpoints for ${monthName} ${currentYear}.`
      });
    } catch (err: any) {
      console.error("[Calendar] Hydration failed:", err);
      setError(err.message);
      setEvents([]);
    } finally {
      setIsLoading(false);
    }
  };

  // Initial fetch on dates changes
  useEffect(() => {
    fetchMonthEvents();
  }, [currentDate, monthName, currentYear]);

  // Hook into custom 'refresh-calendar' window event to trigger instant visual reload of grid
  useEffect(() => {
    const handleRefresh = () => {
      fetchMonthEvents();
    };
    window.addEventListener('refresh-calendar', handleRefresh);
    return () => window.removeEventListener('refresh-calendar', handleRefresh);
  }, [currentDate]);

  // 4. Matrix Generator Engine
  const generateGridDays = () => {
    const year = currentDate.getFullYear();
    const month = currentDate.getMonth();

    const firstDayOfMonth = new Date(year, month, 1);
    let startDayOfWeek = firstDayOfMonth.getDay() - 1;
    if (startDayOfWeek === -1) startDayOfWeek = 6;

    const daysInCurrent = new Date(year, month + 1, 0).getDate();
    const daysInPrev = new Date(year, month, 0).getDate();

    const matrix: { date: Date; isCurrentMonth: boolean; isToday: boolean }[] = [];
    const now = new Date();

    // Pad Preceding Month
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const d = new Date(year, month - 1, daysInPrev - i);
      matrix.push({ date: d, isCurrentMonth: false, isToday: isSameDay(d, now) });
    }

    // Append Current Month
    for (let i = 1; i <= daysInCurrent; i++) {
      const d = new Date(year, month, i);
      matrix.push({ date: d, isCurrentMonth: true, isToday: isSameDay(d, now) });
    }

    // Pad Proceeding Month
    const totalRemaining = 42 - matrix.length; // Standard 6-row grid
    for (let i = 1; i <= totalRemaining; i++) {
      const d = new Date(year, month + 1, i);
      matrix.push({ date: d, isCurrentMonth: false, isToday: isSameDay(d, now) });
    }

    return matrix;
  };

  const isSameDay = (d1: Date, d2: Date) => {
    return d1.getFullYear() === d2.getFullYear() &&
           d1.getMonth() === d2.getMonth() &&
           d1.getDate() === d2.getDate();
  };

  // 5. Day Filter Engine
  const getEventsForDay = (targetDate: Date) => {
    return events.filter(ev => {
      const dateStr = ev.start?.dateTime || ev.start?.date;
      if (!dateStr) return false;
      const evDate = new Date(dateStr);
      return isSameDay(evDate, targetDate);
    });
  };

  // Nav Actions
  const shiftMonth = (dir: number) => {
    setCurrentDate(prev => new Date(prev.getFullYear(), prev.getMonth() + dir, 1));
  };

  const setToday = () => {
    setCurrentDate(new Date());
  };

  const gridDays = generateGridDays();

  return (
    <div className="w-full h-full flex flex-col bg-mono-50 dark:bg-black overflow-hidden relative font-sans select-none">
      
      {/* Decorative Vector Background Accents */}
      <div className="absolute top-0 right-0 w-[500px] h-[500px] bg-gradient-to-bl from-white/5 to-transparent rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-[500px] h-[500px] bg-gradient-to-tr from-white/5 to-transparent rounded-full blur-3xl pointer-events-none" />

      {/* CALENDAR HEADER */}
      <header className="flex items-center justify-between py-6 px-8 bg-white dark:bg-[#080808] border-b border-mono-200/50 dark:border-mono-900/60 shadow-sm z-10 relative">
        <div className="flex items-center gap-4">
          <div className="p-3 rounded-xl bg-mono-100 dark:bg-mono-900 border border-mono-200/50 dark:border-mono-800/60">
            <CalendarIcon className="text-mono-900 dark:text-white w-5 h-5" />
          </div>
          <div>
            <h1 className="text-2xl font-black tracking-tight text-mono-900 dark:text-white font-mono uppercase">
              {monthName} <span className="text-mono-400 dark:text-mono-600">{currentYear}</span>
            </h1>
            <p className="text-xs text-mono-400 font-mono mt-0.5 uppercase tracking-widest">Interactive Schedule Matrix</p>
          </div>
        </div>

        <div className="flex items-center gap-3 bg-mono-50 dark:bg-[#121212] border border-mono-200/60 dark:border-mono-900 p-1.5 rounded-xl">
          <button 
            onClick={() => shiftMonth(-1)} 
            className="p-2 hover:bg-white dark:hover:bg-mono-850 text-mono-500 hover:text-mono-900 dark:hover:text-white rounded-lg transition-all active:scale-95 border border-transparent hover:border-mono-200/50 dark:hover:border-mono-800"
          >
            <ChevronLeft size={18} />
          </button>
          <button 
            onClick={setToday} 
            className="px-4 py-1 text-xs font-bold tracking-wider font-mono uppercase text-mono-700 dark:text-mono-400 hover:bg-white hover:text-black dark:hover:bg-white dark:hover:text-black rounded-lg border border-transparent hover:border-mono-200/50 dark:hover:border-mono-800 transition-all active:scale-95"
          >
            Today
          </button>
          <button 
            onClick={() => shiftMonth(1)} 
            className="p-2 hover:bg-white dark:hover:bg-mono-850 text-mono-500 hover:text-mono-900 dark:hover:text-white rounded-lg transition-all active:scale-95 border border-transparent hover:border-mono-200/50 dark:hover:border-mono-800"
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </header>

      {/* SUB-MESSAGE ALERT STATE */}
      {error && (
        <div className="bg-amber-500/10 border-b border-amber-500/20 px-8 py-2.5 flex items-center gap-2 text-amber-600 dark:text-amber-400 text-xs font-mono z-10">
          <AlertCircle size={14} />
          <span>Warning: {error} Link account to write events.</span>
        </div>
      )}

      {/* GRID MATRIX COMPONENT */}
      <main className="flex-1 flex flex-col p-8 overflow-hidden relative z-10">
        
        {/* Day Headers */}
        <div className="grid grid-cols-7 mb-2 gap-3">
          {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day) => (
            <div key={day} className="text-center py-2 text-[10px] font-mono uppercase tracking-widest font-black text-mono-400 dark:text-mono-600">
              {day}
            </div>
          ))}
        </div>

        {/* Calendar Dynamic Grid */}
        <div className="flex-1 grid grid-cols-7 grid-rows-6 gap-3 relative min-h-0">
          
          {/* Global Overlay Spinner */}
          {isLoading && (
            <div className="absolute inset-0 bg-mono-50/60 dark:bg-black/60 backdrop-blur-[2px] flex items-center justify-center z-30 rounded-2xl border border-mono-200/40 dark:border-mono-900/50 transition-all">
              <div className="bg-white dark:bg-mono-900 border border-mono-200 dark:border-mono-800 px-6 py-4 rounded-2xl shadow-2xl flex items-center gap-3">
                <Loader2 size={20} className="animate-spin text-mono-900 dark:text-white" />
                <span className="text-xs font-mono uppercase font-bold tracking-widest text-mono-900 dark:text-mono-200">Synchronizing Schedule Grid</span>
              </div>
            </div>
          )}

          {gridDays.map(({ date, isCurrentMonth, isToday }, idx) => {
            const dayEvents = getEventsForDay(date);
            const dateId = `day-${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
            
            return (
              <motion.div 
                key={idx} 
                layoutId={dateId}
                onClick={() => setSelectedDay(date)}
                className={`flex flex-col group/cell bg-white dark:bg-[#0d0d0d] border transition-all duration-300 relative overflow-hidden rounded-xl cursor-pointer ${
                  isCurrentMonth 
                    ? 'border-mono-200/60 dark:border-mono-900 shadow-[0_2px_8px_rgba(0,0,0,0.01)]' 
                    : 'border-mono-200/20 dark:border-mono-950 opacity-30'
                } ${
                  isToday 
                    ? 'ring-2 ring-mono-900 dark:ring-white border-transparent scale-[1.01] z-10 shadow-lg' 
                    : 'hover:border-mono-400 dark:hover:border-mono-700 hover:shadow-md'
                }`}
              >
                {/* Corner Date Badge */}
                <div className="flex items-center justify-between p-2.5 pb-1">
                  <span className={`text-[11px] font-bold font-mono flex items-center justify-center w-6 h-6 rounded-lg transition-colors ${
                    isToday 
                      ? 'bg-mono-950 text-white dark:bg-white dark:text-mono-950 shadow-sm font-black' 
                      : 'text-mono-500 dark:text-mono-400 group-hover/cell:text-mono-900 dark:group-hover/cell:text-white'
                  }`}>
                    {date.getDate()}
                  </span>
                  {dayEvents.length > 0 && (
                    <span className="text-[8px] font-mono text-mono-400 dark:text-mono-500 uppercase bg-mono-50 dark:bg-mono-900 px-1.5 py-0.5 rounded border border-mono-200/40 dark:border-mono-800/50">
                      {dayEvents.length} ITEM{dayEvents.length > 1 ? 'S' : ''}
                    </span>
                  )}
                </div>

                {/* Day Individual Event Strip Stack */}
                <div className="flex-1 flex flex-col gap-1 p-2 pt-0 overflow-hidden min-h-0">
                  {dayEvents.slice(0, 4).map((ev, eventIdx) => {
                    return (
                      <div 
                        key={ev.id || eventIdx}
                        className="px-2 py-1 rounded bg-mono-50 dark:bg-mono-950 border border-mono-200/40 dark:border-mono-900 flex flex-col relative group/event overflow-hidden"
                      >
                        <div className="absolute left-0 top-0 bottom-0 w-0.5 bg-mono-900 dark:bg-mono-100" />
                        <span className="text-[8px] font-bold text-mono-800 dark:text-mono-200 truncate leading-snug pl-1">
                          {ev.summary}
                        </span>
                      </div>
                    );
                  })}
                  {dayEvents.length > 4 && (
                    <p className="text-[7px] font-mono text-mono-400 mt-0.5 text-center uppercase tracking-tighter">
                      + {dayEvents.length - 4} more
                    </p>
                  )}
                </div>

              </motion.div>
            );
          })}
        </div>
      </main>

      {/* Day View Zoom Overlay */}
      <AnimatePresence>
        {selectedDay && (
          <DayViewOverlay 
            date={selectedDay} 
            events={getEventsForDay(selectedDay)} 
            onClose={() => setSelectedDay(null)} 
            onRefresh={fetchMonthEvents}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

interface DayViewOverlayProps {
  date: Date;
  events: CalendarEvent[];
  onClose: () => void;
  onRefresh: () => void;
}

function DayViewOverlay({ date, events, onClose, onRefresh }: DayViewOverlayProps) {
  const dateId = `day-${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
  const dayName = date.toLocaleDateString('default', { weekday: 'long' });
  const dateLabel = date.toLocaleDateString('default', { month: 'long', day: 'numeric', year: 'numeric' });

  // Separate all-day from timed events
  const [localEvents, setLocalEvents] = useState<CalendarEvent[]>(events);
  const [isDraggingId, setIsDraggingId] = useState<string | null>(null);

  // Modals for Creation and Editing
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createStartTime, setCreateStartTime] = useState('09:00');
  const [createEndTime, setCreateEndTime] = useState('10:00');
  const [createSummary, setCreateSummary] = useState('');
  const [createDescription, setCreateDescription] = useState('');
  const [createLocation, setCreateLocation] = useState('');

  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);
  const [editStartTime, setEditStartTime] = useState('09:00');
  const [editEndTime, setEditEndTime] = useState('10:00');
  const [editSummary, setEditSummary] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editLocation, setEditLocation] = useState('');

  const [isMutating, setIsMutating] = useState(false);

  // Sync events from parent updates
  useEffect(() => {
    setLocalEvents(events);
  }, [events]);

  const allDayEvents = localEvents.filter(ev => !ev.start.dateTime);
  const timedEvents = localEvents.filter(ev => ev.start.dateTime);

  // Hourly grid 
  const hours = Array.from({ length: 24 }, (_, i) => i);

  const getPosition = (dateTimeStr?: string) => {
    if (!dateTimeStr) return 0;
    const d = new Date(dateTimeStr);
    if (isNaN(d.getTime())) return 0;
    return (d.getHours() * 60 + d.getMinutes()) / (24 * 60) * 100;
  };

  const getDurationPercent = (start?: string, end?: string) => {
    if (!start || !end) return 4;
    const s = new Date(start);
    const e = new Date(end);
    if (isNaN(s.getTime()) || isNaN(e.getTime())) return 4;
    const diff = (e.getTime() - s.getTime()) / (1000 * 60);
    return (diff / (24 * 60)) * 100;
  };

  // Dragging event positions physically
  const handleDragStart = (e: React.MouseEvent, ev: CalendarEvent) => {
    e.stopPropagation();
    
    const startStr = ev.start?.dateTime;
    const endStr = ev.end?.dateTime;
    if (!startStr || !endStr) return;

    setIsDraggingId(ev.id);

    const start = new Date(startStr);
    const end = new Date(endStr);
    const duration = end.getTime() - start.getTime();

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const timelineElement = document.getElementById('timeline-drag-boundary');
      if (!timelineElement) return;

      const rect = timelineElement.getBoundingClientRect();
      const relativeY = moveEvent.clientY - rect.top;
      
      // Snapping granularity: 15 minutes (50px per hour means 12.5px per 15 minutes)
      const hoursFromTop = relativeY / 50;
      const msFromTop = hoursFromTop * 60 * 60 * 1000;

      const newStart = new Date(date);
      newStart.setHours(0, 0, 0, 0);
      newStart.setTime(newStart.getTime() + msFromTop);

      // Snap start to nearest 15 minutes
      const snappedMinutes = Math.round(newStart.getMinutes() / 15) * 15;
      newStart.setMinutes(snappedMinutes, 0, 0);

      // Cap drag inside the 24 hour day bounds
      if (newStart.getDate() !== date.getDate()) {
        if (newStart.getTime() < date.getTime()) {
          newStart.setHours(0, 0, 0, 0);
        } else {
          newStart.setHours(23, 45, 0, 0);
        }
      }

      const newEnd = new Date(newStart.getTime() + duration);

      setLocalEvents(prev => prev.map(item => {
        if (item.id === ev.id) {
          return {
            ...item,
            start: { dateTime: newStart.toISOString() },
            end: { dateTime: newEnd.toISOString() }
          };
        }
        return item;
      }));
    };

    const handleMouseUp = async () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
      setIsDraggingId(null);

      const finalEvent = localEvents.find(item => item.id === ev.id);
      if (!finalEvent || !finalEvent.start.dateTime || !finalEvent.end.dateTime) return;

      try {
        const res = await fetch(`${API_BASE_URL}/calendar/events/${ev.id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            start_iso: finalEvent.start.dateTime,
            end_iso: finalEvent.end.dateTime
          })
        });
        if (res.ok) {
          onRefresh();
          window.dispatchEvent(new CustomEvent('refresh-calendar'));
        } else {
          // Revert on failure
          setLocalEvents(events);
        }
      } catch (err) {
        console.error("[Calendar] Drag save error:", err);
        setLocalEvents(events);
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
  };

  // Clicking empty timeline to create event
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (e.target !== e.currentTarget) return;

    const rect = e.currentTarget.getBoundingClientRect();
    const clickY = e.clientY - rect.top;
    const clickHourFraction = clickY / 50; // 50px per hour

    const targetHour = Math.floor(clickHourFraction);
    const targetMinutes = Math.floor((clickHourFraction - targetHour) * 4) * 15;

    const startObj = new Date(date);
    startObj.setHours(targetHour, targetMinutes, 0, 0);
    
    const endObj = new Date(startObj);
    endObj.setHours(startObj.getHours() + 1);

    const padZero = (n: number) => n.toString().padStart(2, '0');
    setCreateStartTime(`${padZero(startObj.getHours())}:${padZero(startObj.getMinutes())}`);
    setCreateEndTime(`${padZero(endObj.getHours())}:${padZero(endObj.getMinutes())}`);
    setCreateSummary('');
    setCreateDescription('');
    setCreateLocation('');
    setCreateModalOpen(true);
  };

  // Create event submission
  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!createSummary.trim()) return;

    setIsMutating(true);
    const [startHour, startMin] = createStartTime.split(':').map(Number);
    const [endHour, endMin] = createEndTime.split(':').map(Number);

    const startObj = new Date(date);
    startObj.setHours(startHour, startMin, 0, 0);

    const endObj = new Date(date);
    endObj.setHours(endHour, endMin, 0, 0);

    try {
      const res = await fetch(`${API_BASE_URL}/calendar/events/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary: createSummary,
          start_iso: startObj.toISOString(),
          end_iso: endObj.toISOString(),
          description: createDescription || undefined,
          location: createLocation || undefined
        })
      });

      if (res.ok) {
        setCreateModalOpen(false);
        onRefresh();
        window.dispatchEvent(new CustomEvent('refresh-calendar'));
      }
    } catch (err) {
      console.error("[Calendar] Create event failed:", err);
    } finally {
      setIsMutating(false);
    }
  };

  // Triggering edit modal
  const triggerEdit = (ev: CalendarEvent) => {
    if (!ev.start.dateTime || !ev.end.dateTime) return; // ignore all day events for edit
    setEditEvent(ev);
    
    const startObj = new Date(ev.start.dateTime);
    const endObj = new Date(ev.end.dateTime);
    const padZero = (n: number) => n.toString().padStart(2, '0');
    
    setEditStartTime(`${padZero(startObj.getHours())}:${padZero(startObj.getMinutes())}`);
    setEditEndTime(`${padZero(endObj.getHours())}:${padZero(endObj.getMinutes())}`);
    setEditSummary(ev.summary || '');
    setEditDescription(ev.description || '');
    setEditLocation(ev.location || '');
  };

  // Update event submission
  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editEvent || !editSummary.trim()) return;

    setIsMutating(true);
    const [startHour, startMin] = editStartTime.split(':').map(Number);
    const [endHour, endMin] = editEndTime.split(':').map(Number);

    const startObj = new Date(date);
    startObj.setHours(startHour, startMin, 0, 0);

    const endObj = new Date(date);
    endObj.setHours(endHour, endMin, 0, 0);

    try {
      const res = await fetch(`${API_BASE_URL}/calendar/events/${editEvent.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary: editSummary,
          start_iso: startObj.toISOString(),
          end_iso: endObj.toISOString(),
          description: editDescription || undefined,
          location: editLocation || undefined
        })
      });

      if (res.ok) {
        setEditEvent(null);
        onRefresh();
        window.dispatchEvent(new CustomEvent('refresh-calendar'));
      }
    } catch (err) {
      console.error("[Calendar] Update event failed:", err);
    } finally {
      setIsMutating(false);
    }
  };

  // Delete event submission
  const handleDeleteSubmit = async () => {
    if (!editEvent) return;

    setIsMutating(true);
    try {
      const res = await fetch(`${API_BASE_URL}/calendar/events/${editEvent.id}`, {
        method: 'DELETE'
      });

      if (res.ok) {
        setEditEvent(null);
        onRefresh();
        window.dispatchEvent(new CustomEvent('refresh-calendar'));
      }
    } catch (err) {
      console.error("[Calendar] Delete event failed:", err);
    } finally {
      setIsMutating(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      className="absolute inset-0 z-50 flex items-center justify-center p-8 bg-mono-50/40 dark:bg-black/40 backdrop-blur-sm"
    >
      <motion.div 
        layoutId={dateId}
        className="w-full max-w-4xl h-full bg-white dark:bg-[#080808] border border-mono-200 dark:border-mono-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col"
      >
        <header className="p-6 border-b border-mono-200 dark:border-mono-900 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-12 h-12 rounded-2xl bg-mono-900 dark:bg-white flex flex-col items-center justify-center text-white dark:text-mono-900 shadow-lg">
              <span className="text-[10px] font-mono uppercase font-black leading-none">{date.toLocaleDateString('default', { weekday: 'short' })}</span>
              <span className="text-xl font-black leading-none mt-1">{date.getDate()}</span>
            </div>
            <div>
              <h2 className="text-lg font-black font-mono uppercase text-mono-900 dark:text-white leading-none">{dayName}</h2>
              <p className="text-[10px] font-mono uppercase text-mono-400 mt-1.5 tracking-widest">{dateLabel}</p>
            </div>
          </div>
          <button 
            onClick={onClose}
            className="p-3 hover:bg-mono-50 dark:hover:bg-mono-900 rounded-2xl text-mono-400 hover:text-mono-900 dark:hover:text-white transition-all border border-transparent hover:border-mono-200 dark:hover:border-mono-800"
          >
            <X size={20} />
          </button>
        </header>

        {/* All Day Pinned Section */}
        {allDayEvents.length > 0 && (
          <div className="px-6 py-4 bg-mono-50/50 dark:bg-mono-900/30 border-b border-mono-100 dark:border-mono-900 flex flex-col gap-2">
            <span className="text-[8px] font-mono font-black uppercase text-mono-400 tracking-tighter">All Day Events</span>
            <div className="flex flex-wrap gap-2">
              {allDayEvents.map((ev, idx) => (
                <div 
                  key={ev.id || idx}
                  className="px-3 py-1.5 bg-mono-900 dark:bg-white rounded-lg flex items-center gap-2 shadow-sm"
                >
                  <div className="w-1 h-1 rounded-full bg-white dark:bg-mono-900" />
                  <span className="text-[10px] font-black uppercase font-mono text-white dark:text-mono-900">
                    {ev.summary}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="flex-1 overflow-y-auto custom-scrollbar relative p-6">
          <div 
            id="timeline-drag-boundary"
            onClick={handleTimelineClick}
            className="relative h-[1200px] w-full border-l border-mono-100 dark:border-mono-900 ml-16 cursor-crosshair group/timeline hover:bg-mono-50/10 dark:hover:bg-mono-950/10 transition-colors"
          >
            {/* Click to Create Floating Hint */}
            <div className="absolute left-4 top-2 pointer-events-none opacity-0 group-hover/timeline:opacity-100 transition-opacity duration-300 text-[8px] font-mono uppercase tracking-widest text-mono-400 bg-white/80 dark:bg-black/80 px-2 py-1 rounded border border-mono-200 dark:border-mono-800 shadow-sm">
              💡 Click empty row to Schedule manual checkpoint
            </div>

            {/* Hour markers */}
            {hours.map(hour => (
              <div 
                key={hour} 
                className="absolute w-full border-t border-mono-100 dark:border-mono-900/40 flex items-start pointer-events-none"
                style={{ top: `${(hour / 24) * 100}%`, height: `${(1 / 24) * 100}%` }}
              >
                <span className="absolute -left-16 top-0 -translate-y-1/2 text-[9px] font-mono font-bold text-mono-400 dark:text-mono-500 uppercase w-12 text-right pr-2">
                  {hour === 0 ? '12 AM' : hour < 12 ? `${hour} AM` : hour === 12 ? '12 PM' : `${hour - 12} PM`}
                </span>
              </div>
            ))}

            {/* Timed Event Blocks */}
            {timedEvents.map((ev, idx) => {
              const startPos = getPosition(ev.start.dateTime);
              const duration = getDurationPercent(ev.start.dateTime, ev.end.dateTime);
              const isShort = duration < 6;
              const isDragging = isDraggingId === ev.id;

              return (
                <div 
                  key={ev.id || idx}
                  onMouseDown={(e) => handleDragStart(e, ev)}
                  onClick={(e) => {
                    e.stopPropagation(); // Stop timeline creation click
                    triggerEdit(ev);
                  }}
                  className={`absolute left-2 right-4 rounded-xl border p-2.5 flex flex-col shadow-sm transition-shadow group/ev-block overflow-hidden cursor-grab active:cursor-grabbing ${
                    isDragging 
                      ? 'bg-mono-100/90 dark:bg-mono-900/90 border-mono-900 dark:border-white shadow-xl scale-[1.01] z-[40]' 
                      : 'bg-white dark:bg-[#111] border-mono-200 dark:border-mono-800 hover:border-mono-400 dark:hover:border-mono-700 hover:shadow-md'
                  }`}
                  style={{ 
                    top: `${startPos}%`, 
                    height: `${Math.max(duration, isShort ? 6 : duration)}%`,
                    zIndex: 10 + idx
                  }}
                >
                  <div className="absolute left-0 top-0 bottom-0 w-1 rounded-l-xl bg-mono-900 dark:bg-white" />
                  <span className="text-[10px] font-black uppercase font-mono truncate leading-none text-mono-900 dark:text-white">
                    {ev.summary}
                  </span>
                  <div className="flex items-center gap-1.5 mt-1 text-[8px] font-mono font-bold text-mono-400 uppercase tracking-tighter">
                    <Clock size={7} />
                    <span>
                      {new Date(ev.start.dateTime!).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                      {' - '}
                      {new Date(ev.end.dateTime!).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}
                    </span>
                  </div>
                  {ev.description && !isShort && (
                    <p className="text-[8px] text-mono-400 dark:text-mono-500 mt-2 line-clamp-2 leading-relaxed italic">
                      {ev.description}
                    </p>
                  )}
                  
                  {/* Subtle drag handle visual hint */}
                  <div className="absolute right-2 top-2 opacity-0 group-hover/ev-block:opacity-100 transition-opacity flex flex-col gap-0.5 pointer-events-none">
                    <div className="w-2.5 h-0.5 bg-mono-300 dark:bg-mono-700 rounded" />
                    <div className="w-2.5 h-0.5 bg-mono-300 dark:bg-mono-700 rounded" />
                    <div className="w-2.5 h-0.5 bg-mono-300 dark:bg-mono-700 rounded" />
                  </div>
                </div>
              );
            })}

            {/* Current Time Indicator if selected day is today */}
            {new Date().toDateString() === date.toDateString() && (
              <div 
                className="absolute w-full h-[2px] bg-red-500 z-[100] pointer-events-none flex items-center"
                style={{ top: `${getPosition(new Date().toISOString())}%` }}
              >
                <div className="w-2.5 h-2.5 rounded-full bg-red-500 -ml-1.25 shadow-[0_0_10px_rgba(239,68,68,0.5)]" />
                <div className="absolute right-0 mr-2 px-1.5 py-0.5 bg-red-500 text-white text-[7px] font-mono font-black uppercase rounded shadow-lg">NOW</div>
              </div>
            )}
          </div>
        </div>
      </motion.div>

      {/* CREATE EVENT MODAL OVERLAY */}
      <AnimatePresence>
        {createModalOpen && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-[200] select-none">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-[#0d0d0d] border border-mono-200 dark:border-mono-800 max-w-md w-full rounded-2xl shadow-2xl overflow-hidden"
            >
              <div className="p-5 border-b border-mono-200 dark:border-mono-900 bg-mono-50 dark:bg-black/40 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <Plus className="text-mono-900 dark:text-white" size={18} />
                  <span className="text-xs font-mono uppercase font-bold tracking-wider text-mono-900 dark:text-white">Schedule Event</span>
                </div>
                <button onClick={() => setCreateModalOpen(false)} className="p-1 hover:bg-mono-200 dark:hover:bg-mono-800 rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white">
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleCreateSubmit} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">Event Title *</label>
                  <input 
                    type="text" 
                    required
                    placeholder="Standup, Project Sync, etc."
                    value={createSummary}
                    onChange={(e) => setCreateSummary(e.target.value)}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">Start Time</label>
                    <div className="relative">
                      <input 
                        type="time" 
                        required
                        value={createStartTime}
                        onChange={(e) => setCreateStartTime(e.target.value)}
                        className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">End Time</label>
                    <div className="relative">
                      <input 
                        type="time" 
                        required
                        value={createEndTime}
                        onChange={(e) => setCreateEndTime(e.target.value)}
                        className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                      />
                    </div>
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400 flex items-center gap-1.5"><MapPin size={11}/> Location</label>
                  <input 
                    type="text" 
                    placeholder="Virtual / Meeting Room / Cafe"
                    value={createLocation}
                    onChange={(e) => setCreateLocation(e.target.value)}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400 flex items-center gap-1.5"><AlignLeft size={11}/> Description</label>
                  <textarea 
                    placeholder="Meeting agendas, notes, links..."
                    value={createDescription}
                    onChange={(e) => setCreateDescription(e.target.value)}
                    rows={2}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white resize-none"
                  />
                </div>

                <div className="pt-2 flex gap-3">
                  <button 
                    type="button" 
                    onClick={() => setCreateModalOpen(false)}
                    className="flex-1 py-2 text-[10px] font-mono font-black uppercase tracking-wider rounded-lg border border-mono-200 hover:bg-mono-50 dark:border-mono-800 dark:hover:bg-mono-900 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={isMutating}
                    className="flex-1 py-2 text-[10px] font-mono font-black uppercase tracking-wider rounded-lg bg-mono-900 text-white dark:bg-white dark:text-mono-950 hover:bg-black dark:hover:bg-mono-100 flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                  >
                    {isMutating ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    <span>Confirm</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* EDIT/DELETE EVENT MODAL OVERLAY */}
      <AnimatePresence>
        {editEvent && (
          <div className="fixed inset-0 bg-black/60 backdrop-blur-md flex items-center justify-center p-4 z-[200] select-none">
            <motion.div 
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              className="bg-white dark:bg-[#0d0d0d] border border-mono-200 dark:border-mono-800 max-w-md w-full rounded-2xl shadow-2xl overflow-hidden"
            >
              <div className="p-5 border-b border-mono-200 dark:border-mono-900 bg-mono-50 dark:bg-black/40 flex items-center justify-between">
                <span className="text-xs font-mono uppercase font-bold tracking-wider text-mono-900 dark:text-white">Modify Event Details</span>
                <button onClick={() => setEditEvent(null)} className="p-1 hover:bg-mono-200 dark:hover:bg-mono-800 rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white">
                  <X size={16} />
                </button>
              </div>

              <form onSubmit={handleEditSubmit} className="p-5 space-y-4">
                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">Event Title *</label>
                  <input 
                    type="text" 
                    required
                    value={editSummary}
                    onChange={(e) => setEditSummary(e.target.value)}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">Start Time</label>
                    <input 
                      type="time" 
                      required
                      value={editStartTime}
                      onChange={(e) => setEditStartTime(e.target.value)}
                      className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400">End Time</label>
                    <input 
                      type="time" 
                      required
                      value={editEndTime}
                      onChange={(e) => setEditEndTime(e.target.value)}
                      className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400 flex items-center gap-1.5"><MapPin size={11}/> Location</label>
                  <input 
                    type="text" 
                    placeholder="Virtual / Meeting Room / Cafe"
                    value={editLocation}
                    onChange={(e) => setEditLocation(e.target.value)}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-[9px] font-mono uppercase font-black tracking-wider text-mono-400 flex items-center gap-1.5"><AlignLeft size={11}/> Description</label>
                  <textarea 
                    placeholder="Meeting agendas, notes, links..."
                    value={editDescription}
                    onChange={(e) => setEditDescription(e.target.value)}
                    rows={2}
                    className="w-full text-xs font-mono p-2.5 rounded-lg border border-mono-200 dark:border-mono-800 bg-transparent text-mono-900 dark:text-white focus:outline-none focus:border-mono-900 dark:focus:border-white resize-none"
                  />
                </div>

                <div className="pt-2 flex gap-3">
                  <button 
                    type="button" 
                    onClick={handleDeleteSubmit}
                    disabled={isMutating}
                    className="py-2 px-4 text-[10px] font-mono font-black uppercase tracking-wider rounded-lg border border-red-200 text-red-500 hover:bg-red-50 dark:border-red-900/50 dark:hover:bg-red-950/20 flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <Trash2 size={13} />
                    <span>Delete</span>
                  </button>
                  <button 
                    type="button" 
                    onClick={() => setEditEvent(null)}
                    className="flex-1 py-2 text-[10px] font-mono font-black uppercase tracking-wider rounded-lg border border-mono-200 dark:border-mono-800 hover:bg-mono-50 dark:hover:bg-mono-900 transition-colors"
                  >
                    Cancel
                  </button>
                  <button 
                    type="submit"
                    disabled={isMutating}
                    className="flex-1 py-2 text-[10px] font-mono font-black uppercase tracking-wider rounded-lg bg-mono-900 text-white dark:bg-white dark:text-mono-950 hover:bg-black dark:hover:bg-mono-100 flex items-center justify-center gap-2 transition-all shadow-md active:scale-95"
                  >
                    {isMutating ? <Loader2 size={12} className="animate-spin" /> : <Save size={12} />}
                    <span>Save</span>
                  </button>
                </div>
              </form>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
