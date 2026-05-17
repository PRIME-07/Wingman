
import { useChatStore } from '../stores/useChatStore';
import { Activity, Database, Cpu, Wrench, AlertTriangle, CheckCircle2, ChevronRight, X } from 'lucide-react';
import type { TelemetryEvent } from '../types';


export function TelemetryPane() {
  const { telemetry, clearTelemetry, isTelemetryOpen, toggleTelemetry } = useChatStore();

  if (!isTelemetryOpen) return null;

  return (
    <aside className="w-80 border-l border-mono-200/60 dark:border-mono-900/50 bg-white dark:bg-[#000000] h-full flex flex-col animate-in slide-in-from-right duration-300 relative z-10">
      {/* Absolute border separator for premium feel */}
      <div className="absolute inset-y-0 left-0 w-[1px] bg-gradient-to-b from-transparent via-mono-200 dark:via-mono-800 to-transparent pointer-events-none" />
      
      {/* Panel Title */}
      <div className="p-4 border-b border-mono-200 dark:border-mono-900 flex items-center justify-between">
        <div className="flex items-center gap-2 text-xs font-bold tracking-wider font-mono uppercase text-mono-700 dark:text-mono-300">
          <Activity size={14} className="text-mono-500 animate-pulse" />
          Telemetry Deck
        </div>
        <div className="flex items-center gap-2">
          <button 
            onClick={clearTelemetry}
            className="text-[10px] font-mono text-mono-400 hover:text-mono-800 dark:hover:text-mono-100 tracking-tight px-1.5 py-0.5 rounded hover:bg-mono-100 dark:hover:bg-mono-900 transition-colors"
          >
            CLEAR
          </button>
          <button 
            onClick={toggleTelemetry}
            className="text-mono-400 hover:text-mono-700 dark:hover:text-mono-200 transition-colors p-0.5"
          >
            <X size={15} />
          </button>
        </div>
      </div>

      {/* Stream Contents */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 scrollbar-thin">
        {telemetry.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-center opacity-40 select-none py-12">
            <Cpu size={36} strokeWidth={1} className="mb-3" />
            <span className="text-xs font-mono font-medium uppercase tracking-widest">Awaiting Activity</span>
            <span className="text-[10px] tracking-tight mt-1">Execute prompts to initialize trace tracking.</span>
          </div>
        ) : (
          telemetry.map((evt) => <TelemetryCard key={evt.id} event={evt} />)
        )}
      </div>
    </aside>
  );
}

function TelemetryCard({ event }: { event: TelemetryEvent }) {
  const iconMap = {
    node_entry: <Cpu size={12} className="text-mono-500" />,
    node_exit: <CheckCircle2 size={12} className="text-mono-500" />,
    tool_start: <Wrench size={12} className="text-mono-700 dark:text-mono-300 animate-spin-slow" />,
    tool_end: <CheckCircle2 size={12} className="text-mono-500" />,
    retrieval: <Database size={12} className="text-mono-700 dark:text-mono-300" />,
    error: <AlertTriangle size={12} className="text-red-500 animate-bounce" />,
    info: <ChevronRight size={12} className="text-mono-400" />,
    stream_chunk: <ChevronRight size={12} />,
    emotion_update: <Activity size={12} className="text-mono-500" />,
    graph_started: <Cpu size={12} className="text-mono-500" />,
    graph_completed: <CheckCircle2 size={12} className="text-mono-500" />,
    llm_started: <Cpu size={12} className="text-mono-500" />,
    llm_completed: <CheckCircle2 size={12} className="text-mono-500" />
  };

  const timeStr = new Date(event.timestamp).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });

  return (
    <div className={`p-2.5 rounded border bg-white dark:bg-mono-950/80 font-mono flex flex-col text-[11px] transition-all duration-200 shadow-sm ${
      event.type === 'error' 
        ? 'border-red-200 dark:border-red-900/30 bg-red-50/20 dark:bg-red-950/10' 
        : 'border-mono-200 dark:border-mono-900/60'
    }`}>
      <div className="flex items-center justify-between mb-1">
        <div className="flex items-center gap-1.5">
          <span className="p-1 rounded bg-mono-100 dark:bg-mono-900 flex items-center justify-center">
            {iconMap[event.type] || iconMap.info}
          </span>
          <span className="font-bold uppercase tracking-wider text-[10px] text-mono-800 dark:text-mono-200">
            {event.label}
          </span>
        </div>
        <span className="text-[9px] text-mono-400 opacity-80">{timeStr}</span>
      </div>
      
      <p className="text-mono-600 dark:text-mono-300 leading-relaxed break-words mt-0.5">
        {event.message}
      </p>

      {/* Small collapsible metadata tag (if properties exist) */}
      {event.payload && Object.keys(event.payload).length > 0 && (
        <div className="mt-2 bg-mono-50 dark:bg-black/40 rounded p-1.5 overflow-x-auto border border-mono-200/30 dark:border-mono-900/50 max-h-28">
          <pre className="text-[9px] text-mono-400 leading-tight">
            {JSON.stringify(event.payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
}
