import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { MessageSquare, Search, Folder, Plug, Calendar, Paperclip, Moon, Sun, FileText, Upload, Trash2, Loader2, Pencil, Check, X, ExternalLink, Sheet, Users, Mail, Phone, Plus } from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';

const BACKEND_HOST = import.meta.env.VITE_BACKEND_URL || 'localhost:8000';
const HTTP_PROTOCOL = window.location.protocol === 'https:' ? 'https:' : 'http:';
const API_BASE_URL = `${HTTP_PROTOCOL}//${BACKEND_HOST}/api/v1`;

interface DocumentRecord {
  doc_id: string;
  filename: string;
  file_size: number;
  chunk_count: number;
  uploaded_at: string;
  metadata?: {
    asset_type?: string;
    url?: string;
    virtual?: boolean;
  };
}

interface SessionRecord {
  session_id: string;
  session_name: string;
  created_at: string;
  updated_at: string;
}

interface ContactRecord {
  contact_id: string;
  name: string;
  alias?: string;
  email?: string;
  phone?: string;
}

const MarqueeText = ({ text, className = "text-[10px] font-bold" }: { text: string, className?: string }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLParagraphElement>(null);
  const [distance, setDistance] = useState(0);

  useEffect(() => {
    if (containerRef.current && contentRef.current) {
      const containerWidth = containerRef.current.offsetWidth;
      const contentWidth = contentRef.current.scrollWidth;
      if (contentWidth > containerWidth) {
        setDistance(containerWidth - contentWidth - 20); // 20px padding for the fade
      } else {
        setDistance(0);
      }
    }
  }, [text]);

  return (
    <div
      ref={containerRef}
      className={`marquee-container flex-1 min-w-0 ${distance < 0 ? 'text-fade-right' : ''}`}
      style={{ '--scroll-distance': `${distance}px`, '--scroll-duration': `${Math.max(3, Math.abs(distance) / 30)}s` } as any}
    >
      <p
        ref={contentRef}
        className={`font-mono dark:text-mono-100 marquee-content ${distance < 0 ? 'marquee-active' : ''} ${className}`}
      >
        {text}
      </p>
    </div>
  );
};

export function Sidebar() {
  const {
    theme,
    toggleTheme,
    addTelemetry,
    telemetry,
    currentSessionId,
    setCurrentSessionId,
    isStreaming,
    activeSidebarTab: activeTab,
    setActiveSidebarTab: setActiveTab,
    setAuthPromptOpen
  } = useChatStore();

  // Global context arrays
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [sessions, setSessions] = useState<SessionRecord[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState<string>('');
  const [deleteConfirmDoc, setDeleteConfirmDoc] = useState<{ docId: string; filename: string } | null>(null);
  const [deleteConfirmSessionId, setDeleteConfirmSessionId] = useState<string | null>(null);
  const [deleteConfirmContact, setDeleteConfirmContact] = useState<{ id: string; name: string } | null>(null);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStageText, setUploadStageText] = useState('Deep Scanning Node...');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Search feature state variables
  const [searchText, setSearchText] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [searchResults, setSearchResults] = useState<{
    uploadedDocs: any[];
    googleDocs: any[];
    googleSheets: any[];
    calendarEvents: any[];
  } | null>(null);

  // Tools integration state
  const [tools, setTools] = useState<{ name: string; description: string }[]>([]);
  const [isLoadingTools, setIsLoadingTools] = useState(false);

  // Contacts feature state variables
  const [contacts, setContacts] = useState<ContactRecord[]>([]);
  const [isLoadingContacts, setIsLoadingContacts] = useState(false);
  const [isContactModalOpen, setIsContactModalOpen] = useState(false);
  const [editingContact, setEditingContact] = useState<ContactRecord | null>(null);
  const [contactForm, setContactForm] = useState({ name: '', alias: '', email: '', phone: '' });

  const fetchContacts = async () => {
    try {
      setIsLoadingContacts(true);
      const res = await fetch(`${API_BASE_URL}/contacts`);
      if (res.ok) {
        const data = await res.json();
        setContacts(data);
      }
    } catch (err) {
      console.error("Contacts fetch error:", err);
    } finally {
      setIsLoadingContacts(false);
    }
  };

  const startAddContact = () => {
    setEditingContact(null);
    setContactForm({ name: '', alias: '', email: '', phone: '' });
    setIsContactModalOpen(true);
  };

  const startEditContact = (contact: ContactRecord) => {
    setEditingContact(contact);
    setContactForm({
      name: contact.name,
      alias: contact.alias || '',
      email: contact.email || '',
      phone: contact.phone || ''
    });
    setIsContactModalOpen(true);
  };

  const handleSaveContact = async () => {
    if (!contactForm.name.trim()) return;
    try {
      const url = editingContact 
        ? `${API_BASE_URL}/contacts/${editingContact.contact_id}` 
        : `${API_BASE_URL}/contacts`;
      const method = editingContact ? 'PATCH' : 'POST';
      
      const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: contactForm.name.trim(),
          alias: contactForm.alias.trim() || undefined,
          email: contactForm.email.trim() || undefined,
          phone: contactForm.phone.trim() || undefined
        })
      });
      
      if (res.ok) {
        setIsContactModalOpen(false);
        fetchContacts();
        addTelemetry({
          type: 'info',
          label: 'Contacts',
          message: editingContact ? `Updated contact '${contactForm.name}'.` : `Created contact '${contactForm.name}'.`
        });
      }
    } catch (err) {
      console.error("Save contact error:", err);
    }
  };

  const handleDeleteContact = (contactId: string, contactName: string) => {
    setDeleteConfirmContact({ id: contactId, name: contactName });
  };

  const confirmDeleteContact = async () => {
    if (!deleteConfirmContact) return;
    const { id, name } = deleteConfirmContact;
    try {
      const res = await fetch(`${API_BASE_URL}/contacts/${id}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        fetchContacts();
        addTelemetry({
          type: 'info',
          label: 'Contacts',
          message: `Deleted contact '${name}'.`
        });
      }
    } catch (err) {
      console.error("Delete contact error:", err);
    } finally {
      setDeleteConfirmContact(null);
    }
  };

  const fetchSessions = async () => {
    try {
      setIsLoadingSessions(true);
      const res = await fetch(`${API_BASE_URL}/sessions`);
      if (res.ok) {
        const data = await res.json();
        setSessions(data);
      }
    } catch (err) {
      console.error("Session fetch error:", err);
    } finally {
      setIsLoadingSessions(false);
    }
  };

  useEffect(() => {
    fetchDocuments();
    fetchSessions();
  }, []);

  // 1. Hot-Reload Vault / Contacts on active toggle
  useEffect(() => {
    if (activeTab === 'vault') {
      fetchDocuments();
    } else if (activeTab === 'contacts') {
      fetchContacts();
    }
  }, [activeTab]);

  // 2. Load Registered Assistant Tools
  const fetchTools = async () => {
    try {
      setIsLoadingTools(true);
      const res = await fetch(`${API_BASE_URL}/tools`);
      if (res.ok) {
        const data = await res.json();
        setTools(data);
      }
    } catch (err) {
      console.error("Registry fetch failure:", err);
    } finally {
      setIsLoadingTools(false);
    }
  };

  useEffect(() => {
    if (activeTab === 'integrations' && tools.length === 0) {
      fetchTools();
    }
  }, [activeTab, tools.length]);

  // 3. Multi-Domain Live Search with 350ms debounce debounce
  useEffect(() => {
    if (activeTab !== 'search') return;
    if (!searchText.trim()) {
      setSearchResults(null);
      return;
    }

    const delayDebounceFn = setTimeout(async () => {
      try {
        setIsSearching(true);
        const res = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(searchText.trim())}`);
        if (res.ok) {
          const data = await res.json();
          setSearchResults(data);
        }
      } catch (err) {
        console.error("Search failure:", err);
      } finally {
        setIsSearching(false);
      }
    }, 350);

    return () => clearTimeout(delayDebounceFn);
  }, [searchText, activeTab]);

  const prevStreaming = useRef(isStreaming);
  useEffect(() => {
    let timer: any = null;
    if (prevStreaming.current && !isStreaming) {
      // Re-hydrate sessions list when a generation finishes, cementing the virtual session!
      fetchSessions();

      // Delayed fetch to catch the backend's async Progressive Naming Title upgrade!
      timer = setTimeout(() => {
        fetchSessions();
      }, 2500);
    }
    prevStreaming.current = isStreaming;
    return () => {
      if (timer) clearTimeout(timer);
    };
  }, [isStreaming]);

  // 3. Listen for Backend Pipeline Progress via Telemetry
  useEffect(() => {
    const latest = telemetry[0]; // Newest is first in store
    if (latest && latest.payload?.backend_type === 'doc_ingest_progress') {
      const { progress, stage } = latest.payload;
      setUploadProgress(progress);
      if (stage) {
        setUploadStageText(stage);
      }
    }
  }, [telemetry]);

  const fetchDocuments = async () => {
    try {
      setIsLoadingDocs(true);
      const res = await fetch(`${API_BASE_URL}/documents`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data);
      }
    } catch (err) {
      console.error("Catalog error:", err);
    } finally {
      setIsLoadingDocs(false);
    }
  };



  const triggerUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const formData = new FormData();
    formData.append('file', file);
    if (currentSessionId) {
      formData.append('session_id', currentSessionId);
    }

    try {
      setUploadStatus('uploading');
      setUploadProgress(0);
      setUploadStageText('Streaming to Pipeline...');
      setIsUploading(true);

      addTelemetry({
        type: 'info',
        label: 'Document Pipeline',
        message: `Streaming '${file.name}' to vector engine...`,
      });

      // Use XHR for progress tracking
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/documents/upload`, true);

      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable) {
          // Client-side upload is only the first 20% of the visual progress
          const percent = Math.round((event.loaded / event.total) * 20);
          setUploadProgress(percent);
        }
      };

      const uploadPromise = new Promise((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            reject(new Error(`Upload failed with status ${xhr.status}`));
          }
        };
        xhr.onerror = () => reject(new Error("Network error during upload."));
        xhr.send(formData);
      });

      const data: any = await uploadPromise;

      setUploadStatus('success');
      addTelemetry({
        type: 'retrieval',
        label: 'Pinecone Index',
        message: `Ingested '${file.name}' successfully (${data.chunks} chunks).`,
      });
      fetchDocuments();

      // Reset after a delay
      setTimeout(() => setUploadStatus('idle'), 3000);
    } catch (err: any) {
      setUploadStatus('error');
      addTelemetry({ type: 'error', label: 'Pipeline Alert', message: err.message });
      setTimeout(() => setUploadStatus('idle'), 3000);
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = (e: React.MouseEvent, docId: string, filename: string) => {
    e.stopPropagation();
    setDeleteConfirmDoc({ docId, filename });
  };

  const confirmDelete = async () => {
    if (!deleteConfirmDoc) return;
    const { docId, filename } = deleteConfirmDoc;

    try {
      const res = await fetch(`${API_BASE_URL}/documents/${docId}`, { method: 'DELETE' });
      if (res.ok) {
        addTelemetry({ type: 'info', label: 'Purged', message: `Erased ${filename}.` });
        setDocuments(prev => prev.filter(d => d.doc_id !== docId));
      }
    } catch (err) {
      console.error(err);
    } finally {
      setDeleteConfirmDoc(null);
    }
  };

  const [syncingAssets, setSyncingAssets] = useState<Set<string>>(new Set());

  const handleSyncAsset = async (assetId: string, assetType: string, title: string) => {
    try {
      setSyncingAssets(prev => new Set(prev).add(assetId));
      addTelemetry({
        type: 'info',
        label: 'Memory Sync',
        message: `Bridging '${title}' to semantic vault...`,
      });

      const res = await fetch(`${API_BASE_URL}/documents/sync`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id: assetId,
          asset_type: assetType,
          title: title,
          session_id: currentSessionId
        })
      });

      if (res.ok) {
        addTelemetry({
          type: 'retrieval',
          label: 'Pinecone Sync',
          message: `Successfully indexed '${title}' for context retrieval.`,
        });
        fetchDocuments(); // Refresh vault list
      } else {
        throw new Error("Sync failed.");
      }
    } catch (err: any) {
      addTelemetry({ type: 'error', label: 'Sync Alert', message: err.message });
    } finally {
      setSyncingAssets(prev => {
        const next = new Set(prev);
        next.delete(assetId);
        return next;
      });
    }
  };

  const createSession = () => {
    // Instantiate client-side session pointer only (lazy persistence prevents empty sessions)
    const newId = (typeof crypto !== 'undefined' && crypto.randomUUID)
      ? crypto.randomUUID()
      : Math.random().toString(36).substring(2, 15) + Math.random().toString(36).substring(2, 15);
    setCurrentSessionId(newId);
  };

  const deleteSession = (e: React.MouseEvent, sessionId: string) => {
    e.stopPropagation();
    setDeleteConfirmSessionId(sessionId);
  };

  const confirmDeleteSession = async () => {
    if (!deleteConfirmSessionId) return;
    const sessionId = deleteConfirmSessionId;
    setDeleteConfirmSessionId(null);

    const exists = sessions.some(s => s.session_id === sessionId);
    if (!exists) {
      if (currentSessionId === sessionId) {
        const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
        setCurrentSessionId(newId);
      }
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, { method: 'DELETE' });
      if (res.ok) {
        setSessions(prev => prev.filter(s => s.session_id !== sessionId));
        if (currentSessionId === sessionId) {
          const newId = crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).substring(2, 15);
          setCurrentSessionId(newId);
        }
      }
    } catch (err) {
      console.error("Delete session error:", err);
    }
  };

  const startRenameSession = (e: React.MouseEvent, sessionId: string, currentName: string) => {
    e.stopPropagation();
    setEditingSessionId(sessionId);
    setEditingName(currentName);
  };

  const submitRenameSession = async (sessionId: string) => {
    if (!editingName || editingName.trim() === '') {
      setEditingSessionId(null);
      return;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/sessions/${sessionId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_name: editingName.trim() })
      });
      if (res.ok) {
        const updatedSession = await res.json();
        setSessions(prev => prev.map(s => s.session_id === sessionId ? updatedSession : s));
        addTelemetry({
          type: 'info',
          label: 'Session Engine',
          message: `Renamed session to '${editingName.trim()}'.`
        });
      }
    } catch (err) {
      console.error("Rename session error:", err);
    } finally {
      setEditingSessionId(null);
    }
  };

  const formatBytes = (bytes: number) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  };

  // Small Mascot Avatar for the very top of sidebar activity bar
  const mascotIconSrc = `/expressions/happy_${theme === 'dark' ? 'd' : 'l'}.png`;

  return (
    <div className="h-full flex select-none z-20 relative shrink-0">

      {/* 1. ULTRA-THIN ACTIVITY BAR (LEFTMOST) */}
      <aside className="w-16 bg-white dark:bg-[#000000] h-full flex flex-col items-center justify-between py-5 border-r border-mono-200/50 dark:border-mono-900/60 transition-colors shadow-[4px_0_12px_rgba(0,0,0,0.02)] dark:shadow-[4px_0_16px_rgba(0,0,0,0.4)]">

        {/* Top Grouping */}
        <div className="flex flex-col items-center w-full gap-6">
          {/* Small Mascot Head Toggle */}
          <button
            onClick={() => setActiveTab(activeTab === 'chat' ? null : 'chat')}
            className="relative w-10 h-10 flex items-center justify-center rounded-lg transition-transform active:scale-95"
          >
            <img
              src={mascotIconSrc}
              className={`w-7 h-7 object-contain transition-opacity ${activeTab === 'chat' ? 'opacity-100' : 'opacity-70 hover:opacity-90'}`}
              alt="Mascot"
            />
          </button>

          <div className="w-6 h-[1px] bg-mono-200/40 dark:bg-mono-800/50" />

          {/* Main Tabs */}
          <div className="flex flex-col items-center w-full gap-3">
            {[
              { id: 'vault', icon: Paperclip },
              { id: 'search', icon: Search },
              { id: 'chat', icon: MessageSquare },
              { id: 'folder', icon: Folder },
              { id: 'integrations', icon: Plug },
              { id: 'contacts', icon: Users },
              { id: 'timers', icon: Calendar },
            ].map((tab) => {
              const Icon = tab.icon;
              const isCurrent = activeTab === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(isCurrent ? null : (tab.id as any))}
                  className={`w-10 h-10 flex items-center justify-center rounded-lg transition-all duration-200 border relative ${isCurrent
                    ? 'bg-mono-50 dark:bg-mono-900 border-mono-200/60 dark:border-mono-800/80 shadow-sm'
                    : 'border-transparent hover:bg-mono-50/50 dark:hover:bg-mono-900/40 hover:border-mono-200/30 dark:hover:border-mono-800/30'
                    }`}
                >
                  <Icon
                    size={18}
                    className={`transition-colors ${isCurrent ? 'text-mono-900 dark:text-white' : 'text-mono-400 dark:text-mono-500 hover:text-mono-700 dark:hover:text-mono-300'}`}
                  />
                  {isCurrent && (
                    <div className="absolute left-0 top-1/2 -translate-y-1/2 w-0.5 h-5 bg-mono-900 dark:bg-white rounded-r" />
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Bottom Grouping */}
        <div className="flex flex-col items-center gap-4 w-full pb-4">
          {/* Theme Toggle */}
          <button
            onClick={toggleTheme}
            className="w-8 h-8 flex items-center justify-center rounded-full text-mono-400 hover:text-mono-900 dark:hover:text-white transition-colors hover:bg-mono-50 dark:hover:bg-mono-900/60"
          >
            {theme === 'dark' ? <Sun size={14} /> : <Moon size={14} />}
          </button>
        </div>
      </aside>

      {/* 2. EXPANDABLE PRIMARY DRAWER (SUB-PANE) */}
      <AnimatePresence>
        {activeTab && activeTab !== 'timers' && (
          <motion.div
            initial={{ width: 0 }}
            animate={{ width: 288 }}
            exit={{ width: 0 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className="bg-mono-50 dark:bg-[#000000] border-r border-mono-200/60 dark:border-mono-900/80 h-full flex flex-col overflow-hidden flex-shrink-0"
          >
            <div className="w-72 h-full flex flex-col flex-shrink-0">

              {/* Chat / Sessions Drawer */}
              {activeTab === 'chat' ? (
                <div className="flex-1 flex flex-col h-full">
                  <div className="p-4 border-b border-mono-200/60 dark:border-mono-900">
                    <h3 className="text-[10px] font-mono uppercase tracking-widest font-bold text-mono-800 dark:text-mono-300">
                      Sessions
                    </h3>
                  </div>

                  <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                    {/* Primary 'New Session' Action Card */}
                    <button
                      onClick={createSession}
                      className="w-full py-3 px-4 rounded transition-all active:scale-[0.98] flex items-center justify-center mb-4 bg-mono-950 dark:bg-white hover:bg-black dark:hover:bg-mono-50 text-white dark:text-mono-950 shadow-md border border-transparent"
                    >
                      <div className="flex items-center gap-3 justify-center">
                        <MessageSquare className="w-4 h-4" />
                        <span className="text-[11px] font-bold tracking-wide uppercase text-center">New Session</span>
                      </div>
                    </button>

                    {isLoadingSessions ? (
                      <div className="text-center py-8 text-[10px] font-mono text-mono-400">LOCKED ON TARGET...</div>
                    ) : sessions.length === 0 ? (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic">No sessions found.</div>
                    ) : (
                      sessions.map((session) => (
                        <div
                          key={session.session_id}
                          onClick={() => {
                            if (editingSessionId !== session.session_id) {
                              setCurrentSessionId(session.session_id);
                            }
                          }}
                          className={`group p-3 rounded border transition-all cursor-pointer relative ${currentSessionId === session.session_id
                            ? 'bg-white dark:bg-mono-900 border-mono-300 dark:border-mono-800 shadow-sm'
                            : 'border-transparent hover:bg-white/50 dark:hover:bg-mono-900/30 hover:border-mono-200/60 dark:hover:border-mono-800/50'
                            }`}
                        >
                          {editingSessionId === session.session_id ? (
                            <div className="flex items-center gap-1.5 w-full" onClick={(e) => e.stopPropagation()}>
                              <input
                                type="text"
                                autoFocus
                                value={editingName}
                                onChange={(e) => setEditingName(e.target.value)}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter') submitRenameSession(session.session_id);
                                  if (e.key === 'Escape') setEditingSessionId(null);
                                }}
                                className="w-full bg-white dark:bg-mono-900 border border-mono-300 dark:border-mono-700 rounded px-1.5 py-0.5 text-[11px] font-medium focus:outline-none text-mono-900 dark:text-white"
                              />
                              <div className="flex items-center gap-1 flex-shrink-0">
                                <button
                                  onClick={() => submitRenameSession(session.session_id)}
                                  className="text-green-600 dark:text-green-400 hover:scale-110 transition-all"
                                  title="Confirm"
                                >
                                  <Check size={12} />
                                </button>
                                <button
                                  onClick={() => setEditingSessionId(null)}
                                  className="text-mono-400 hover:text-red-500 hover:scale-110 transition-all"
                                  title="Cancel"
                                >
                                  <X size={12} />
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="flex items-center justify-between gap-2">
                              <span className="text-[11px] font-medium truncate dark:text-mono-200">
                                {session.session_name}
                              </span>
                              {currentSessionId === session.session_id && (
                                <div className="flex items-center gap-1.5 opacity-0 group-hover:opacity-100 transition-opacity flex-shrink-0">
                                  <button
                                    onClick={(e) => startRenameSession(e, session.session_id, session.session_name)}
                                    className="text-mono-400 hover:text-mono-900 dark:hover:text-white transition-colors"
                                    title="Rename Session"
                                  >
                                    <Pencil size={11} />
                                  </button>
                                  <button
                                    onClick={(e) => deleteSession(e, session.session_id)}
                                    className="text-mono-400 hover:text-red-500 transition-colors"
                                    title="Delete Session"
                                  >
                                    <Trash2 size={11} />
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                          <div className="text-[9px] text-mono-400 mt-1">
                            {new Date(session.updated_at).toLocaleDateString()}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : activeTab === 'vault' || activeTab === 'folder' ? (
                <div className="flex-1 flex flex-col h-full">
                  <div className="p-4 border-b border-mono-200/60 dark:border-mono-900 flex items-center justify-between">
                    <h3 className="text-[10px] font-mono uppercase tracking-widest font-bold text-mono-800 dark:text-mono-300">
                      Semantic Vault
                    </h3>
                    <button
                      onClick={triggerUpload}
                      disabled={isUploading}
                      className="w-6 h-6 flex items-center justify-center rounded bg-mono-900 dark:bg-white text-white dark:text-mono-950 hover:scale-105 transition-all disabled:opacity-50"
                    >
                      {isUploading ? <Loader2 size={10} className="animate-spin" /> : <Upload size={10} />}
                    </button>
                    <input type="file" ref={fileInputRef} className="hidden" accept=".pdf,.docx,.doc,.txt,.md,.markdown" onChange={handleFileChange} />
                  </div>

                  <div className="flex-1 overflow-y-auto p-3 space-y-3 custom-scrollbar">
                    {/* Upload Progress Overlay */}
                    {uploadStatus !== 'idle' && (
                      <motion.div
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        className={`p-6 rounded-2xl border-2 mb-4 transition-all duration-500 shadow-xl flex flex-col gap-5 ${uploadStatus === 'uploading' ? 'border-mono-200 dark:border-mono-800 bg-mono-50/50 dark:bg-mono-900/20' :
                            uploadStatus === 'success' ? 'border-green-500/50 bg-green-500/10' :
                              'border-red-500/50 bg-red-500/10'
                          }`}
                      >
                        <div className="flex flex-col items-center justify-center">
                          <motion.span
                            key={uploadProgress}
                            initial={{ opacity: 0, y: 5 }}
                            animate={{ opacity: 1, y: 0 }}
                            className="text-4xl font-mono font-bold text-mono-900 dark:text-white tracking-tighter"
                          >
                            {uploadProgress}%
                          </motion.span>
                          <span className="text-[8px] font-mono text-mono-400 uppercase tracking-[0.2em] mt-1 font-bold">
                            {uploadStatus === 'uploading' ? 'Neural Sync Active' : 'Operation Finalized'}
                          </span>
                        </div>

                        <div className="w-full h-2 bg-mono-200 dark:bg-mono-800 rounded-full overflow-hidden shadow-inner relative">
                          <motion.div
                            initial={{ width: 0 }}
                            animate={{ width: `${uploadProgress}%` }}
                            className={`h-full transition-all duration-300 ${uploadStatus === 'success' ? 'bg-green-500' :
                                uploadStatus === 'error' ? 'bg-red-500' : 'bg-mono-900 dark:bg-white shadow-[0_0_15px_rgba(255,255,255,0.6)]'
                              }`}
                          />
                        </div>

                        <div className="flex flex-col items-center">
                          <span className={`text-[11px] font-mono font-bold uppercase tracking-tight text-center leading-tight ${uploadStatus === 'success' ? 'text-green-500' :
                              uploadStatus === 'error' ? 'text-red-500' : 'text-mono-800 dark:text-mono-100'
                            }`}>
                            {uploadStatus === 'uploading' ? uploadStageText :
                              uploadStatus === 'success' ? 'Vectorization Complete' : 'Pipeline Critical Fault'}
                          </span>
                          {uploadStatus === 'uploading' && (
                            <div className="flex gap-1 mt-2">
                              {[1, 2, 3].map(i => (
                                <motion.div
                                  key={i}
                                  animate={{ opacity: [0.3, 1, 0.3] }}
                                  transition={{ duration: 1.5, repeat: Infinity, delay: i * 0.2 }}
                                  className="w-1 h-1 rounded-full bg-mono-400"
                                />
                              ))}
                            </div>
                          )}
                        </div>
                      </motion.div>
                    )}

                    {isLoadingDocs ? (
                      <div className="text-center py-8 text-[10px] font-mono text-mono-400 animate-pulse tracking-widest uppercase">
                        Indexing Engine...
                      </div>
                    ) : documents.length === 0 ? (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic border border-dashed border-mono-200 dark:border-mono-800 rounded-lg bg-mono-100/20 dark:bg-black/10">
                        Vault is empty
                      </div>
                    ) : (
                      <div className="grid gap-2">
                        {documents.map(doc => {
                          const isGoogleDoc = doc.metadata?.asset_type === 'google_doc';
                          const isGoogleSheet = doc.metadata?.asset_type === 'google_sheet';
                          const extension = doc.filename.split('.').pop()?.toLowerCase();

                          const Icon = isGoogleDoc ? FileText : isGoogleSheet ? Sheet : extension === 'pdf' ? FileText : FileText;
                          const iconColor = isGoogleDoc ? 'text-blue-500' : isGoogleSheet ? 'text-green-500' : 'text-mono-400';

                          return (
                            <div
                              key={doc.doc_id}
                              className="group p-3 rounded-xl bg-white dark:bg-[#080808] border border-mono-200/60 dark:border-mono-800 shadow-sm hover:border-mono-900 dark:hover:border-white transition-all ring-1 ring-transparent hover:ring-mono-900/5 dark:hover:ring-white/5 overflow-hidden"
                            >
                              <div className="flex items-start gap-3 justify-between">
                                <div className="flex-1 min-w-0 pr-1">
                                  <div className="flex items-center gap-2 mb-1">
                                    <div className={`w-6 h-6 rounded-lg bg-mono-50 dark:bg-mono-900 flex items-center justify-center ${iconColor}`}>
                                      <Icon size={12} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <MarqueeText text={doc.filename} />
                                      <div className="flex items-center gap-2 text-[8px] font-mono text-mono-400 uppercase tracking-tighter">
                                        <span>{formatBytes(doc.file_size)}</span>
                                        <span className="w-0.5 h-0.5 rounded-full bg-mono-300" />
                                        <span>{doc.chunk_count} Blocks</span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                <button
                                  onClick={(e) => handleDelete(e, doc.doc_id, doc.filename)}
                                  className="w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-red-500 hover:bg-red-50/50 dark:hover:bg-red-950/20 opacity-0 group-hover:opacity-100 transition-all"
                                  title="Purge from Vault"
                                >
                                  <Trash2 size={11} />
                                </button>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              ) : activeTab === 'integrations' ? (
                <div className="flex-1 flex flex-col h-full">
                  <div className="p-4 border-b border-mono-200/60 dark:border-mono-900 flex items-center justify-between">
                    <h3 className="text-[10px] font-mono uppercase tracking-widest font-bold text-mono-800 dark:text-mono-300">
                      Integrations
                    </h3>
                    <button
                      onClick={() => setAuthPromptOpen(true)}
                      className="px-2 py-1 text-[8px] font-mono uppercase tracking-tighter bg-mono-900 dark:bg-white text-white dark:text-mono-950 rounded hover:scale-105 transition-all"
                    >
                      Configure
                    </button>
                  </div>
                  <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                    {isLoadingTools ? (
                      <div className="text-center py-8 text-[10px] font-mono text-mono-400 animate-pulse">LINKING SYSTEM...</div>
                    ) : tools.length === 0 ? (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic">No active plug-ins available.</div>
                    ) : (
                      tools.map((t, idx) => (
                        <div key={idx} className="p-2 border border-mono-200/60 dark:border-mono-900 rounded bg-white dark:bg-[#111] transition-all hover:shadow-sm">
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[10px] font-bold text-mono-900 dark:text-mono-100 uppercase tracking-wider font-mono">{t.name}</span>
                            <div className="flex items-center gap-1.5">
                              <span className="text-[8px] font-mono text-mono-400 dark:text-mono-200 font-semibold tracking-tight">ACTIVE</span>
                              <div className="w-1.5 h-1.5 rounded-full bg-[#00FF00] shadow-[0_0_6px_rgba(0,255,0,0.5)] animate-pulse" />
                            </div>
                          </div>
                          <p className="text-[9px] leading-relaxed text-mono-500 dark:text-mono-400 italic font-sans">
                            {t.description}
                          </p>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : activeTab === 'search' ? (
                <div className="flex-1 flex flex-col h-full">
                  <div className="p-4 border-b border-mono-200/60 dark:border-mono-900 flex flex-col gap-3">
                    <h3 className="text-[10px] font-mono uppercase tracking-widest font-bold text-mono-800 dark:text-mono-300">
                      Global Engine Search
                    </h3>
                    <div className="relative">
                      <input
                        type="text"
                        placeholder="Type to scan nodes..."
                        value={searchText}
                        onChange={(e) => setSearchText(e.target.value)}
                        className="w-full bg-white dark:bg-[#121212] border border-mono-200 dark:border-mono-800 text-[11px] py-1.5 pl-8 pr-3 rounded font-mono outline-none text-mono-900 dark:text-mono-100 placeholder-mono-400 focus:border-mono-400 dark:focus:border-mono-700 transition-colors"
                      />
                      <Search size={12} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-mono-400" />
                    </div>
                  </div>

                  <div className="flex-1 overflow-y-auto p-3 space-y-4 custom-scrollbar">
                    {isSearching ? (
                      <div className="text-center py-8">
                        <div className="inline-block text-[10px] font-mono text-mono-400 animate-pulse">SCANNING DISTRIBUTED MAPS...</div>
                      </div>
                    ) : !searchText ? (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic border border-dashed border-mono-200 dark:border-mono-800 rounded bg-mono-100/10 dark:bg-black/5 px-3">
                        Scan through Vault docs, Google Drive, and Calendar events simultaneously.
                      </div>
                    ) : searchResults &&
                      (searchResults.uploadedDocs.length > 0 ||
                        searchResults.googleDocs.length > 0 ||
                        searchResults.googleSheets.length > 0 ||
                        searchResults.calendarEvents.length > 0) ? (
                      <>
                        {/* Sector 1: System Vault Files */}
                        {searchResults.uploadedDocs.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-[8px] font-mono uppercase font-bold text-mono-400 border-b border-mono-200/50 dark:border-mono-800/50 pb-1 mb-2">
                              SYSTEM VAULT ({searchResults.uploadedDocs.length})
                            </h4>
                            {searchResults.uploadedDocs.map((doc, i) => (
                              <div key={i} className="group p-3 rounded-xl bg-white dark:bg-[#080808] border border-mono-200/60 dark:border-mono-800 shadow-sm hover:border-mono-900 dark:hover:border-white transition-all ring-1 ring-transparent hover:ring-mono-900/5 dark:hover:ring-white/5 overflow-hidden">
                                <div className="flex items-center gap-3">
                                  <div className="w-6 h-6 rounded-lg bg-mono-50 dark:bg-mono-900 flex items-center justify-center text-mono-400">
                                    <FileText size={12} />
                                  </div>
                                  <div className="flex-1 min-w-0">
                                    <MarqueeText text={doc.filename} />
                                    <span className="text-[8px] font-mono text-mono-400 uppercase tracking-tighter">Stored in Matrix</span>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Sector 2: Google Workspace Cloud Docs */}
                        {searchResults.googleDocs.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-[8px] font-mono uppercase font-bold text-mono-400 border-b border-mono-200/50 dark:border-mono-800/50 pb-1 mb-2">
                              GOOGLE DOCS ({searchResults.googleDocs.length})
                            </h4>
                            {searchResults.googleDocs.map((gdoc, i) => (
                              <div key={i} className="group p-3 rounded-xl bg-white dark:bg-[#080808] border border-mono-200/60 dark:border-mono-800 shadow-sm hover:border-mono-900 dark:hover:border-white transition-all ring-1 ring-transparent hover:ring-mono-900/5 dark:hover:ring-white/5 overflow-hidden">
                                <div className="flex items-center gap-3 justify-between">
                                  <div className="flex items-center gap-3 min-w-0 pr-1">
                                    <div className="w-6 h-6 rounded-lg bg-mono-50 dark:bg-mono-900 flex items-center justify-center text-blue-500">
                                      <FileText size={12} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <MarqueeText text={gdoc.name} />
                                      <span className="text-[8px] font-mono text-mono-400 uppercase tracking-tighter">Google Drive</span>
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                      onClick={() => handleSyncAsset(gdoc.id, 'google_doc', gdoc.name)}
                                      disabled={syncingAssets.has(gdoc.id)}
                                      className="w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 disabled:opacity-50"
                                      title="Sync to Vector Vault"
                                    >
                                      {syncingAssets.has(gdoc.id) ? (
                                        <Loader2 size={9} className="animate-spin" />
                                      ) : (
                                        <Paperclip size={10} />
                                      )}
                                    </button>
                                    <a
                                      href={`https://docs.google.com/document/d/${gdoc.id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900"
                                    >
                                      <ExternalLink size={10} />
                                    </a>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Sector 2.5: Google Workspace Cloud Sheets */}
                        {searchResults.googleSheets.length > 0 && (
                          <div className="space-y-2">
                            <h4 className="text-[8px] font-mono uppercase font-bold text-mono-400 border-b border-mono-200/50 dark:border-mono-800/50 pb-1 mb-2">
                              GOOGLE SHEETS ({searchResults.googleSheets.length})
                            </h4>
                            {searchResults.googleSheets.map((gsheet, i) => (
                              <div key={i} className="group p-3 rounded-xl bg-white dark:bg-[#080808] border border-mono-200/60 dark:border-mono-800 shadow-sm hover:border-mono-900 dark:hover:border-white transition-all ring-1 ring-transparent hover:ring-mono-900/5 dark:hover:ring-white/5 overflow-hidden">
                                <div className="flex items-center gap-3 justify-between">
                                  <div className="flex items-center gap-3 min-w-0 pr-1">
                                    <div className="w-6 h-6 rounded-lg bg-mono-50 dark:bg-mono-900 flex items-center justify-center text-green-500">
                                      <Sheet size={12} />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                      <MarqueeText text={gsheet.name} />
                                      <span className="text-[8px] font-mono text-mono-400 uppercase tracking-tighter">Google Sheets</span>
                                    </div>
                                  </div>
                                  <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button
                                      onClick={() => handleSyncAsset(gsheet.id, 'google_sheet', gsheet.name)}
                                      disabled={syncingAssets.has(gsheet.id)}
                                      className="w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 disabled:opacity-50"
                                      title="Sync to Vector Vault"
                                    >
                                      {syncingAssets.has(gsheet.id) ? (
                                        <Loader2 size={9} className="animate-spin" />
                                      ) : (
                                        <Paperclip size={10} />
                                      )}
                                    </button>
                                    <a
                                      href={gsheet.webViewLink || `https://docs.google.com/spreadsheets/d/${gsheet.id}`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900"
                                    >
                                      <ExternalLink size={10} />
                                    </a>
                                  </div>
                                </div>
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Sector 3: Calendar Temporal Matrix */}
                        {searchResults.calendarEvents.length > 0 && (
                          <div className="space-y-1.5">
                            <h4 className="text-[8px] font-mono uppercase font-bold text-mono-400 border-b border-mono-200/50 dark:border-mono-800/50 pb-1 mb-1.5">
                              CALENDAR LOGS ({searchResults.calendarEvents.length})
                            </h4>
                            {searchResults.calendarEvents.map((ev, i) => {
                              const startDate = ev.start?.dateTime || ev.start?.date;
                              const formattedDate = startDate ? new Date(startDate).toLocaleDateString([], { month: 'short', day: 'numeric' }) : 'Date Unspecified';
                              return (
                                <div key={i} className="p-2 bg-white dark:bg-[#111] border border-mono-200/60 dark:border-mono-900 rounded flex flex-col">
                                  <span className="text-[10px] font-medium text-mono-900 dark:text-mono-200 truncate">
                                    {ev.summary}
                                  </span>
                                  <div className="flex items-center gap-1.5 mt-0.5 text-[8px] font-mono text-mono-400">
                                    <Calendar size={8} />
                                    <span>{formattedDate}</span>
                                  </div>
                                </div>
                              );
                            })}
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic border border-mono-100 dark:border-mono-900 bg-white dark:bg-black/10 rounded">
                        No matches in data vectors.
                      </div>
                    )}
                  </div>
                </div>
              ) : activeTab === 'contacts' ? (
                <div className="flex-1 flex flex-col h-full">
                  <div className="p-4 border-b border-mono-200/60 dark:border-mono-900">
                    <h3 className="text-[10px] font-mono uppercase tracking-widest font-bold text-mono-800 dark:text-mono-300">
                      Contacts Directory
                    </h3>
                  </div>

                  <div className="flex-1 overflow-y-auto p-3 space-y-2 custom-scrollbar">
                    {/* Add Contact Action Card */}
                    <button
                      onClick={startAddContact}
                      className="w-full py-2 px-3 rounded transition-all active:scale-[0.98] flex items-center justify-center mb-3 bg-mono-950 dark:bg-white hover:bg-black dark:hover:bg-mono-50 text-white dark:text-mono-950 shadow border border-transparent"
                    >
                      <div className="flex items-center gap-2 justify-center">
                        <Plus className="w-3.5 h-3.5" />
                        <span className="text-[10px] font-bold tracking-wider uppercase text-center">Add Contact</span>
                      </div>
                    </button>

                    {isLoadingContacts ? (
                      <div className="text-center py-8 text-[10px] font-mono text-mono-400">RETRIEVING CONTACTS...</div>
                    ) : contacts.length === 0 ? (
                      <div className="text-center py-8 text-[10px] text-mono-400 italic">No contacts registered.</div>
                    ) : (
                      contacts.map((contact) => (
                        <div
                          key={contact.contact_id}
                          className="group pt-3 px-3 pb-1.5 hover:pb-3 rounded-lg border border-mono-200/60 dark:border-mono-800/80 bg-white dark:bg-[#080808] hover:border-mono-900 dark:hover:border-white transition-all duration-300 flex flex-col overflow-hidden relative shadow-sm hover:shadow-md"
                        >
                          {/* Card Header (Alias/Nickname on top, real name below) */}
                          <div className="flex items-start justify-between gap-3 min-w-0 pr-1">
                            <div className="flex-1 min-w-0">
                              {/* Primary Header - 22px spaced-out font (Alias if present, else Real Name) */}
                              <MarqueeText 
                                text={contact.alias ? contact.alias : contact.name} 
                                className="text-[22px] font-mono font-black uppercase tracking-wider text-mono-950 dark:text-white leading-none" 
                              />
                              {/* Subtitle - 15px font (Real Name if alias exists) */}
                              {contact.alias && (
                                <p className="text-[15px] font-mono font-bold text-mono-500 dark:text-mono-400 mt-1 leading-tight">
                                  {contact.name}
                                </p>
                              )}
                            </div>
                          </div>

                          {/* Hover Expansion Details & Action Icons */}
                          <div className="max-h-0 opacity-0 group-hover:max-h-32 group-hover:opacity-100 transition-all duration-300 ease-in-out overflow-hidden flex flex-col gap-1.5 mt-2 border-t border-mono-100 dark:border-mono-900/60 pt-2">
                            {contact.email && (
                              <div className="flex items-center gap-1.5 text-[11px] font-mono text-mono-400 truncate">
                                <Mail size={12} className="flex-shrink-0" />
                                <span className="truncate">{contact.email}</span>
                              </div>
                            )}
                            {contact.phone && (
                              <div className="flex items-center gap-1.5 text-[11px] font-mono text-mono-400">
                                <Phone size={12} className="flex-shrink-0" />
                                <span>{contact.phone}</span>
                              </div>
                            )}
                            <div className="flex items-center justify-end gap-1.5 mt-0.5">
                              <button
                                onClick={(e) => { e.stopPropagation(); startEditContact(contact); }}
                                className="w-5 h-5 flex items-center justify-center rounded text-mono-400 hover:text-mono-900 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 transition-colors"
                                title="Edit Contact"
                              >
                                <Pencil size={11} />
                              </button>
                              <button
                                onClick={(e) => { e.stopPropagation(); handleDeleteContact(contact.contact_id, contact.name); }}
                                className="w-5 h-5 flex items-center justify-center rounded text-mono-400 hover:text-red-500 hover:bg-mono-50 dark:hover:bg-mono-900 transition-colors"
                                title="Delete Contact"
                              >
                                <Trash2 size={11} />
                              </button>
                            </div>
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ) : null}

              {/* Close Pane handle */}
              <div className="p-2 border-t border-mono-200/60 dark:border-mono-900 text-center">
                <button
                  onClick={() => setActiveTab(null)}
                  className="w-full text-[9px] font-mono font-medium text-mono-400 hover:text-mono-800 dark:hover:text-white transition-colors py-1"
                >
                  COLLAPSE PANE
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {deleteConfirmDoc && (
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            {/* Backdrop with high blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteConfirmDoc(null)}
              className="absolute inset-0 bg-black/60 backdrop-blur-[6px]"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: 'spring', duration: 0.3 }}
              className="relative w-full max-w-sm overflow-hidden rounded-2xl bg-white dark:bg-[#0c0c0c] border border-mono-200/80 dark:border-mono-800/80 p-6 shadow-2xl z-10"
            >
              {/* Top alert border glow effect */}
              <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-red-500/20 via-red-500 to-red-500/20" />

              {/* Close Button */}
              <button
                onClick={() => setDeleteConfirmDoc(null)}
                className="absolute top-4 right-4 w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-800 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 transition-all"
                title="Dismiss"
              >
                <X size={12} />
              </button>

              <div className="flex flex-col items-center text-center">
                {/* Warning icon badge */}
                <div className="w-12 h-12 rounded-full bg-red-500/10 dark:bg-red-500/10 flex items-center justify-center text-red-500 mb-4 border border-red-500/20 animate-pulse">
                  <Trash2 size={20} />
                </div>

                <h3 className="text-xs font-mono font-bold tracking-widest text-mono-900 dark:text-mono-100 uppercase mb-2">
                  CONFIRM VECTOR DESTRUCTION
                </h3>

                <p className="text-[10px] font-mono text-mono-500 dark:text-mono-400 leading-relaxed mb-6">
                  Are you absolutely sure you want to permanently purge <span className="text-red-500 font-bold">"{deleteConfirmDoc.filename}"</span> from the Neural Vector Vault? This action will erase all semantic chunks and is irreversible.
                </p>

                <div className="flex items-center gap-2 w-full">
                  <button
                    onClick={() => setDeleteConfirmDoc(null)}
                    className="flex-1 py-2 px-3 rounded-lg border border-mono-200 dark:border-mono-800 hover:bg-mono-50 dark:hover:bg-mono-900 text-[10px] font-mono font-bold text-mono-600 dark:text-mono-300 transition-all active:scale-[0.98]"
                  >
                    ABORT
                  </button>
                  <button
                    onClick={confirmDelete}
                    className="flex-1 py-2 px-3 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[10px] font-mono font-bold transition-all shadow-md shadow-red-600/20 active:scale-[0.98]"
                  >
                    PURGE MEMORY
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Session Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirmSessionId && (
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            {/* Backdrop with high blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteConfirmSessionId(null)}
              className="absolute inset-0 bg-black/60 backdrop-blur-[6px]"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: 'spring', duration: 0.3 }}
              className="relative w-full max-w-sm overflow-hidden rounded-2xl bg-white dark:bg-[#0c0c0c] border border-mono-200/80 dark:border-mono-800/80 p-6 shadow-2xl z-10"
            >
              {/* Top alert border glow effect */}
              <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-red-500/20 via-red-500 to-red-500/20" />

              {/* Close Button */}
              <button
                onClick={() => setDeleteConfirmSessionId(null)}
                className="absolute top-4 right-4 w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-800 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 transition-all"
                title="Dismiss"
              >
                <X size={12} />
              </button>

              <div className="flex flex-col items-center text-center">
                {/* Warning icon badge */}
                <div className="w-12 h-12 rounded-full bg-red-500/10 dark:bg-red-500/10 flex items-center justify-center text-red-500 mb-4 border border-red-500/20 animate-pulse">
                  <Trash2 size={20} />
                </div>

                <h3 className="text-xs font-mono font-bold tracking-widest text-mono-950 dark:text-mono-100 uppercase mb-2">
                  CONFIRM SESSION REMOVAL
                </h3>

                <p className="text-[10px] font-mono text-mono-500 dark:text-mono-400 leading-relaxed mb-6">
                  Are you absolutely sure you want to permanently delete this chat session? This will purge all message logs from MongoDB and is irreversible.
                </p>

                <div className="flex items-center gap-2 w-full">
                  <button
                    onClick={() => setDeleteConfirmSessionId(null)}
                    className="flex-1 py-2 px-3 rounded-lg border border-mono-200 dark:border-mono-800 hover:bg-mono-50 dark:hover:bg-mono-900 text-[10px] font-mono font-bold text-mono-600 dark:text-mono-300 transition-all active:scale-[0.98]"
                  >
                    ABORT
                  </button>
                  <button
                    onClick={confirmDeleteSession}
                    className="flex-1 py-2 px-3 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[10px] font-mono font-bold transition-all shadow-md shadow-red-600/20 active:scale-[0.98]"
                  >
                    DELETE
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Contact Delete Confirmation Modal */}
      <AnimatePresence>
        {deleteConfirmContact && (
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            {/* Backdrop with high blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setDeleteConfirmContact(null)}
              className="absolute inset-0 bg-black/60 backdrop-blur-[6px]"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: 'spring', duration: 0.3 }}
              className="relative w-full max-w-sm overflow-hidden rounded-2xl bg-white dark:bg-[#0c0c0c] border border-mono-200/80 dark:border-mono-800/80 p-6 shadow-2xl z-10"
            >
              {/* Top alert border glow effect */}
              <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-red-500/20 via-red-500 to-red-500/20" />

              {/* Close Button */}
              <button
                onClick={() => setDeleteConfirmContact(null)}
                className="absolute top-4 right-4 w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-800 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 transition-all"
                title="Dismiss"
              >
                <X size={12} />
              </button>

              <div className="flex flex-col items-center text-center">
                {/* Warning icon badge */}
                <div className="w-12 h-12 rounded-full bg-red-500/10 dark:bg-red-500/10 flex items-center justify-center text-red-500 mb-4 border border-red-500/20 animate-pulse">
                  <Trash2 size={20} />
                </div>

                <h3 className="text-xs font-mono font-bold tracking-widest text-mono-900 dark:text-mono-100 uppercase mb-2">
                  CONFIRM CONTACT REMOVAL
                </h3>

                <p className="text-[10px] font-mono text-mono-500 dark:text-mono-400 leading-relaxed mb-6">
                  Are you absolutely sure you want to permanently delete <span className="text-red-500 font-bold">"{deleteConfirmContact.name}"</span>? This will erase their profile details from database and is irreversible.
                </p>

                <div className="flex items-center gap-2 w-full">
                  <button
                    onClick={() => setDeleteConfirmContact(null)}
                    className="flex-1 py-2 px-3 rounded-lg border border-mono-200 dark:border-mono-800 hover:bg-mono-50 dark:hover:bg-mono-900 text-[10px] font-mono font-bold text-mono-600 dark:text-mono-300 transition-all active:scale-[0.98]"
                  >
                    ABORT
                  </button>
                  <button
                    onClick={confirmDeleteContact}
                    className="flex-1 py-2 px-3 rounded-lg bg-red-600 hover:bg-red-500 text-white text-[10px] font-mono font-bold transition-all shadow-md shadow-red-600/20 active:scale-[0.98]"
                  >
                    DELETE
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* Contact Form Modal */}
      <AnimatePresence>
        {isContactModalOpen && (
          <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4">
            {/* Backdrop with high blur */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setIsContactModalOpen(false)}
              className="absolute inset-0 bg-black/60 backdrop-blur-[6px]"
            />

            {/* Modal Card */}
            <motion.div
              initial={{ scale: 0.95, opacity: 0, y: 10 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 10 }}
              transition={{ type: 'spring', duration: 0.3 }}
              className="relative w-full max-w-sm overflow-hidden rounded-2xl bg-white dark:bg-[#0c0c0c] border border-mono-200/80 dark:border-mono-800/80 p-6 shadow-2xl z-10"
            >
              {/* Top border glow effect */}
              <div className="absolute top-0 inset-x-0 h-[2px] bg-gradient-to-r from-mono-500/20 via-mono-500 to-mono-500/20 dark:from-white/20 dark:via-white dark:to-white/20" />

              {/* Close Button */}
              <button
                onClick={() => setIsContactModalOpen(false)}
                className="absolute top-4 right-4 w-6 h-6 flex items-center justify-center rounded-lg text-mono-400 hover:text-mono-800 dark:hover:text-white hover:bg-mono-50 dark:hover:bg-mono-900 transition-all"
                title="Dismiss"
              >
                <X size={12} />
              </button>

              <div className="flex flex-col">
                <h3 className="text-xs font-mono font-bold tracking-widest text-mono-900 dark:text-mono-100 uppercase mb-4">
                  {editingContact ? 'Edit Contact' : 'Register New Contact'}
                </h3>

                <div className="space-y-3 mb-6">
                  {/* Nickname/Alias */}
                  <div>
                    <label className="text-[8px] font-mono font-bold uppercase tracking-wider text-mono-400 block mb-1">
                      Nickname / Alias (Optional)
                    </label>
                    <input
                      type="text"
                      placeholder="dad"
                      value={contactForm.alias}
                      onChange={(e) => setContactForm({ ...contactForm, alias: e.target.value })}
                      className="w-full bg-mono-50 dark:bg-mono-900/40 border border-mono-200/60 dark:border-mono-800/80 rounded px-2.5 py-1.5 text-[11px] font-medium focus:outline-none focus:border-mono-900 dark:focus:border-white text-mono-900 dark:text-white"
                    />
                  </div>

                  {/* Real Name */}
                  <div>
                    <label className="text-[8px] font-mono font-bold uppercase tracking-wider text-mono-400 block mb-1">
                      Name *
                    </label>
                    <input
                      type="text"
                      placeholder="John Doe"
                      required
                      value={contactForm.name}
                      onChange={(e) => setContactForm({ ...contactForm, name: e.target.value })}
                      className="w-full bg-mono-50 dark:bg-mono-900/40 border border-mono-200/60 dark:border-mono-800/80 rounded px-2.5 py-1.5 text-[11px] font-medium focus:outline-none focus:border-mono-900 dark:focus:border-white text-mono-900 dark:text-white"
                    />
                  </div>

                  {/* Email */}
                  <div>
                    <label className="text-[8px] font-mono font-bold uppercase tracking-wider text-mono-400 block mb-1">
                      Email (Optional)
                    </label>
                    <input
                      type="email"
                      placeholder="john@example.com"
                      value={contactForm.email}
                      onChange={(e) => setContactForm({ ...contactForm, email: e.target.value })}
                      className="w-full bg-mono-50 dark:bg-mono-900/40 border border-mono-200/60 dark:border-mono-800/80 rounded px-2.5 py-1.5 text-[11px] font-medium focus:outline-none focus:border-mono-900 dark:focus:border-white text-mono-900 dark:text-white"
                    />
                  </div>

                  {/* Phone */}
                  <div>
                    <label className="text-[8px] font-mono font-bold uppercase tracking-wider text-mono-400 block mb-1">
                      Phone Number (Optional)
                    </label>
                    <input
                      type="tel"
                      placeholder="+919876543210"
                      value={contactForm.phone}
                      onChange={(e) => setContactForm({ ...contactForm, phone: e.target.value })}
                      className="w-full bg-mono-50 dark:bg-mono-900/40 border border-mono-200/60 dark:border-mono-800/80 rounded px-2.5 py-1.5 text-[11px] font-medium focus:outline-none focus:border-mono-900 dark:focus:border-white text-mono-900 dark:text-white"
                    />
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full">
                  <button
                    onClick={() => setIsContactModalOpen(false)}
                    className="flex-1 py-2 px-3 rounded-lg border border-mono-200 dark:border-mono-800 hover:bg-mono-50 dark:hover:bg-mono-900 text-[10px] font-mono font-bold text-mono-600 dark:text-mono-300 transition-all active:scale-[0.98]"
                  >
                    ABORT
                  </button>
                  <button
                    onClick={handleSaveContact}
                    disabled={!contactForm.name.trim()}
                    className="flex-1 py-2 px-3 rounded-lg bg-mono-950 dark:bg-white hover:bg-black dark:hover:bg-mono-50 text-white dark:text-mono-950 text-[10px] font-mono font-bold transition-all disabled:opacity-50 active:scale-[0.98]"
                  >
                    SAVE CONTACT
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

    </div>
  );
}
