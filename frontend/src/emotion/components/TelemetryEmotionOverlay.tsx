import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useChatStore } from '../../stores/useChatStore';

function getTelemetryDisplayLabel(event: any): string {
  if (!event) return "Typing...";

  const toolName = (event.payload?.tool_name || event.payload?.telemetry_label || event.label || "").toLowerCase();
  const nodeName = (event.payload?.node_name || "").toLowerCase();
  const backendType = (event.payload?.backend_type || "").toLowerCase();

  // Neo4j accessing
  if (
    backendType === "memory_retrieved" ||
    toolName.includes("neo4j") ||
    nodeName.includes("neo4j") ||
    toolName.includes("recollect")
  ) {
    return "Recollecting Memories...";
  }

  // ChromaDB/vector accessing
  if (
    toolName.includes("chromadb") ||
    nodeName.includes("chromadb") ||
    toolName.includes("chroma") ||
    nodeName.includes("chroma") ||
    toolName.includes("vector") ||
    nodeName.includes("vector") ||
    toolName.includes("ingest") ||
    nodeName.includes("ingest")
  ) {
    return "Reading Documents...";
  }

  // Weather tool
  if (toolName.includes("weather") || nodeName.includes("weather")) {
    return "Consulting weather gods...";
  }

  // Web search
  if (
    toolName.includes("web_search") ||
    toolName.includes("websearch") ||
    toolName.includes("search") ||
    nodeName.includes("search")
  ) {
    return "Surfing the web...";
  }

  // Slack tool
  if (toolName.includes("slack") || nodeName.includes("slack")) {
    return "Using Slack...";
  }

  // Gmail / Email
  if (
    toolName.includes("gmail") ||
    nodeName.includes("gmail") ||
    toolName.includes("email") ||
    nodeName.includes("email")
  ) {
    return "Using Gmail...";
  }

  // Google Sheets
  if (
    toolName.includes("sheets") ||
    nodeName.includes("sheets") ||
    toolName.includes("sheet") ||
    nodeName.includes("sheet")
  ) {
    return "Using Google Sheets...";
  }

  // Google Docs
  if (
    toolName.includes("docs") ||
    nodeName.includes("docs") ||
    toolName.includes("doc") ||
    nodeName.includes("doc")
  ) {
    return "Using Google Docs...";
  }

  // Google Calendar
  if (toolName.includes("calendar") || nodeName.includes("calendar")) {
    return "Using Calendar...";
  }

  // YouTube
  if (toolName.includes("youtube") || nodeName.includes("youtube")) {
    return "Using Youtube...";
  }

  // Maps
  if (
    toolName.includes("maps") ||
    nodeName.includes("maps") ||
    toolName.includes("map") ||
    nodeName.includes("map") ||
    toolName.includes("route") ||
    toolName.includes("geocode")
  ) {
    return "Using Maps...";
  }

  // Default typing / fallback
  return "Typing...";
}

export const TelemetryEmotionOverlay: React.FC = () => {
  const { telemetry, isStreaming } = useChatStore();
  
  if (!isStreaming || telemetry.length === 0) return null;
  
  const latest = telemetry[0]; // Telemetry array is prepended, so index 0 holds the latest event
  const label = getTelemetryDisplayLabel(latest);
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
