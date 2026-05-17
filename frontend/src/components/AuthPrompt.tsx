import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, ExternalLink, Hash, CheckCircle2,
  AlertCircle, Send, Key, Cloud, Search, Map, Copy, Check,
  BookOpen, Info, Youtube, Loader2
} from 'lucide-react';
import { useChatStore } from '../stores/useChatStore';

const API_BASE_URL = import.meta.env.VITE_API_URL || 
                     import.meta.env.VITE_API_BASE_URL || 
                     `http://${import.meta.env.VITE_BACKEND_URL || 'localhost:8000'}/api/v1`;

// Local Components
const SecretInput = ({ label, placeholder, value, onChange }: { 
  label: string; 
  placeholder: string; 
  value: string; 
  onChange: (val: string) => void 
}) => (
  <div className="space-y-2">
    <label className="text-[10px] font-bold uppercase opacity-40">{label}</label>
    <div className="relative group">
      <input
        type="password"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-neutral-900 border border-white/10 rounded-lg px-4 py-3 text-sm font-mono outline-none focus:border-white transition-all"
      />
    </div>
  </div>
);

export const AuthPrompt: React.FC = () => {
  const {
    googleConnected, slackConnected, configStatus,
    checkGoogleStatus, checkSlackStatus, fetchConfigStatus,
    saveSecret, theme, isAuthPromptOpen, setAuthPromptOpen
  } = useChatStore();

  const [activeTab, setActiveTab] = useState<'status' | 'slack' | 'google' | 'tools' | 'engine'>('status');

  const [slackToken, setSlackToken] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);



  // Tool keys state
  const [toolKeys, setToolKeys] = useState({
    weather_api_key: '',
    tavily_api_key: '',
    google_maps_api_key: '',
    youtube_api_key: ''
  });


  // Engine state
  const [engineKeys, setEngineKeys] = useState({
    openai_api_key: ''
  });

  // Google keys state
  const [googleKeys, setGoogleKeys] = useState({
    google_client_id: '',
    google_client_secret: ''
  });


  const [verifyingKey, setVerifyingKey] = useState<string | null>(null);
  const [verifiedKeys, setVerifiedKeys] = useState<Record<string, boolean>>({});

  const allToolsVerified = Object.keys(toolKeys).every(k => {
    const mapping: Record<string, string> = {
      weather_api_key: 'weather',
      tavily_api_key: 'search',
      google_maps_api_key: 'maps',
      youtube_api_key: 'youtube'
    };
    return verifiedKeys[k] || configStatus?.tools[mapping[k] as keyof typeof configStatus.tools];
  });

  const isEverythingDone = !!(
    configStatus?.engine?.openai && 
    slackConnected && 
    googleConnected && 
    allToolsVerified
  );

  useEffect(() => {
    if (configStatus) {
      setToolKeys(prev => ({
        weather_api_key: configStatus.tools.weather ? '••••••••' : prev.weather_api_key,
        tavily_api_key: configStatus.tools.search ? '••••••••' : prev.tavily_api_key,
        google_maps_api_key: configStatus.tools.maps ? '••••••••' : prev.google_maps_api_key,
        youtube_api_key: configStatus.tools.youtube ? '••••••••' : prev.youtube_api_key,
      }));
      setEngineKeys(prev => ({
        openai_api_key: configStatus.engine?.openai ? '••••••••' : prev.openai_api_key
      }));
      // Google Keys
      if (configStatus.google.configured) {
        setGoogleKeys({
          google_client_id: '••••••••',
          google_client_secret: '••••••••'
        });
      }
    }
  }, [configStatus]);

  useEffect(() => {
    if (slackConnected) {
      setSlackToken('••••••••');
    }
  }, [slackConnected]);

  useEffect(() => {
    checkGoogleStatus();
    checkSlackStatus();
    fetchConfigStatus();
  }, []);

  useEffect(() => {
    // Only proceed if we have finished fetching initial status from backend
    const isDataLoaded = googleConnected !== null && slackConnected !== null && configStatus !== null;
    if (!isDataLoaded) return;

    // Show prompt only if core config or major connections are missing
    const needsSetup = googleConnected === false || 
      slackConnected === false ||
      !configStatus?.google.configured || 
      !configStatus?.engine?.openai ||
      !allToolsVerified;

    // If everything is done, don't auto-open
    if (needsSetup && !isEverythingDone) {
      setAuthPromptOpen(true);
    }
  }, [googleConnected, slackConnected, configStatus, allToolsVerified, isEverythingDone, setAuthPromptOpen]);

  useEffect(() => {
    setError(null);
  }, [activeTab]);

  const handleCopyManifest = () => {
    const manifest = `display_name: Wingman
features:
  bot_user:
    display_name: Wingman
    always_online: true
oauth_config:
  scopes:
    bot:
      - channels:history
      - groups:history
      - im:history
      - mpim:history
      - channels:read
      - groups:read
      - im:read
      - mpim:read
      - users:read
      - chat:write
      - files:read
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false`;

    navigator.clipboard.writeText(manifest);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSaveSlack = async () => {
    setError(null);
    if (slackToken === '••••••••') {
      setActiveTab('status');
      return;
    }
    if (!slackToken.startsWith('xoxb-')) {
      setError('Slack token must start with xoxb-');
      return;
    }
    setIsSubmitting(true);
    const { success, message } = await saveSecret('slack', { bot_token: slackToken });
    if (success) {
      setSlackToken('');
      await checkSlackStatus();
      setActiveTab('status');
    } else {
      setError(message || 'Failed to save Slack token.');
    }
    setIsSubmitting(false);
  };

  const handleSaveGoogleConfig = async () => {
    setError(null);
    if (googleKeys.google_client_id === '••••••••' && googleKeys.google_client_secret === '••••••••') {
      if (!googleConnected) {
        handleConnectGoogle();
      }
      setActiveTab('status');
      return;
    }
    if (!googleKeys.google_client_id || !googleKeys.google_client_secret) {
      setError('Both Client ID and Secret are required.');
      return;
    }
    
    // Filter out dots to avoid sending dummy values to backend
    const payload = Object.fromEntries(
      Object.entries(googleKeys).filter(([_, v]) => v !== '••••••••')
    );
    
    setIsSubmitting(true);
    const { success, message } = await saveSecret('google_config', payload);
    if (success) {
      await fetchConfigStatus();
      if (!googleConnected) {
        handleConnectGoogle();
      }
      setActiveTab('status');
    } else {
      setError(message || 'Failed to save Google configuration.');
    }
    setIsSubmitting(false);
  };

  const handleVerifySingleTool = async (provider: string, keyName: string, value: string) => {
    if (!value) return;
    if (value === '••••••••') {
      setVerifiedKeys(prev => ({ ...prev, [keyName]: true }));
      return;
    }
    setVerifyingKey(keyName);
    setError(null);
    const { success, message } = await saveSecret(provider, { [keyName]: value });
    if (success) {
      setVerifiedKeys(prev => ({ ...prev, [keyName]: true }));
      await fetchConfigStatus();
    } else {
      setVerifiedKeys(prev => ({ ...prev, [keyName]: false }));
      setError(message || `Failed to verify ${keyName}`);
    }
    setVerifyingKey(null);
  };

  const handleSaveTools = async () => {
    const toolMapping: Record<string, string> = {
      weather_api_key: 'weather',
      tavily_api_key: 'search',
      google_maps_api_key: 'maps',
      youtube_api_key: 'youtube'
    };
    const allVerified = Object.keys(toolKeys).every(k => 
      verifiedKeys[k] || configStatus?.tools[toolMapping[k] as keyof typeof configStatus.tools]
    );
    if (allVerified) {
      setActiveTab('status');
    } else {
      setError('Please verify all API keys before updating the toolbelt.');
    }
  };



  const handleSaveEngine = async () => {
    setError(null);
    if (engineKeys.openai_api_key === '••••••••') {
      setActiveTab('status');
      return;
    }
    setIsSubmitting(true);
    const { success, message } = await saveSecret('engine', { openai_api_key: engineKeys.openai_api_key });
    if (success) {
      await fetchConfigStatus();
      setActiveTab('status');
    } else {
      setError(message || 'Failed to save OpenAI key.');
    }
    setIsSubmitting(false);
  };

  const handleConnectGoogle = () => {
    window.open(`${API_BASE_URL}/auth/google/connect`, '_blank');
    // Poll for status
    const interval = setInterval(async () => {
      await checkGoogleStatus();
      if (googleConnected) {
        clearInterval(interval);
      }
    }, 3000);
  };


  if (!isAuthPromptOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/80 backdrop-blur-md overflow-y-auto">
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          className={`relative w-full max-w-2xl rounded-2xl border ${theme === 'dark' ? 'bg-black border-white/10 text-white' : 'bg-white border-neutral-200 text-black'
            } shadow-2xl overflow-hidden`}
        >
          <button
              onClick={() => setAuthPromptOpen(false)}
              className="absolute top-4 right-4 p-2 text-mono-400 hover:text-white transition-colors"
            >
              <X size={16} />
            </button>
          <div className="flex h-[550px]">
            {/* Sidebar Tabs */}
            <div className={`w-48 border-r ${theme === 'dark' ? 'border-white/10 bg-black' : 'border-neutral-100 bg-neutral-50/50'} p-4 flex flex-col gap-2`}>
              <div 
                onClick={() => { setActiveTab('status'); setError(null); }}
                className={`flex flex-col items-center gap-2 mb-8 cursor-pointer p-2 transition-all ${activeTab === 'status' ? 'opacity-100 scale-110' : 'opacity-40 hover:opacity-100'}`}
              >
                <img src={new URL(`../../assets/excited_${theme === 'dark' ? 'd' : 'l'}.png`, import.meta.url).href} alt="Wingman" className="w-14 h-14 object-contain" />
                <span className="text-sm font-black uppercase tracking-[0.4em] text-white">Wingman</span>
              </div>
              <div className="mt-4 mb-1 px-3 text-[10px] uppercase tracking-widest opacity-40 font-bold">Setup Assistant</div>
              <button
                onClick={() => { setActiveTab('engine'); setError(null); }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${activeTab === 'engine' ? 'bg-white/10 text-white font-bold' : 'opacity-60 hover:opacity-100'}`}
              >
                <Send size={16} /> Engine
              </button>
              <button
                onClick={() => { setActiveTab('slack'); setError(null); }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${activeTab === 'slack' ? 'bg-white/10 text-white font-bold' : 'opacity-60 hover:opacity-100'}`}
              >
                <Hash size={16} /> Slack App
              </button>
              <button
                onClick={() => { setActiveTab('google'); setError(null); }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${activeTab === 'google' ? 'bg-white/10 text-white font-bold' : 'opacity-60 hover:opacity-100'}`}
              >
                <ExternalLink size={16} /> Google API
              </button>
              <button
                onClick={() => { setActiveTab('tools'); setError(null); }}
                className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${activeTab === 'tools' ? 'bg-white/10 text-white font-bold' : 'opacity-60 hover:opacity-100'}`}
              >
                <Cloud size={16} /> Tool Keys
              </button>

              <div className="mt-auto pt-4 border-t border-white/10">
                <p className="text-[9px] text-center font-mono uppercase tracking-widest text-yellow-400 font-bold opacity-80">
                  Setup Mandatory, alternatively set up secrets in .env file
                </p>
              </div>
            </div>

            {/* Main Content Area */}
            <div className="flex-1 p-8 overflow-y-auto bg-black">
              <AnimatePresence mode="wait">
                {activeTab === 'status' && (
                  <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -10 }}>
                    <div className="mb-6 flex justify-between items-end">
                      <div>
                        <h2 className="text-2xl font-black mb-1">Onboarding Center</h2>
                        <p className="text-sm opacity-60">Complete these steps to wake up Wingman's full potential.</p>
                      </div>
                      <a href="https://github.com/PRIME-07/Wingman#detailed-setup-guide" target="_blank" className="flex items-center gap-1 text-[10px] font-bold text-white/40 hover:text-white transition-all uppercase tracking-wider">
                        Full Setup Guide <ExternalLink size={10} />
                      </a>
                    </div>

                    <div className="grid grid-cols-1 gap-4">
                      {!isEverythingDone ? (
                        <>
                          {/* Engine Status */}
                          <div className={`p-4 rounded-xl border flex items-center justify-between ${configStatus?.engine?.openai ? 'bg-white/5 border-white/20' : 'bg-white/5 border-white/10'}`}>
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg ${configStatus?.engine?.openai ? 'bg-white/20 text-white' : 'bg-white/10 text-white'}`}>
                                <Send size={20} />
                              </div>
                              <div>
                                <div className="text-sm font-bold">LLM Engine</div>
                                <div className="text-[10px] opacity-60">{configStatus?.engine?.openai ? 'OpenAI Active' : 'API Key missing'}</div>
                              </div>
                            </div>
                            {!configStatus?.engine?.openai && (
                              <button onClick={() => setActiveTab('engine')} className="px-3 py-1 bg-white text-black text-[10px] font-bold rounded-md uppercase">Configure</button>
                            )}
                            {configStatus?.engine?.openai && <CheckCircle2 className="text-white" size={18} />}
                          </div>

                          {/* Slack Status */}
                          <div className={`p-4 rounded-xl border flex items-center justify-between ${slackConnected ? 'bg-white/5 border-white/20' : 'bg-white/5 border-white/10'}`}>
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg ${slackConnected ? 'bg-white/20 text-white' : 'bg-white/10 text-white'}`}>
                                <Hash size={20} />
                              </div>
                              <div>
                                <div className="text-sm font-bold">Slack Integration</div>
                                <div className="text-[10px] opacity-60">
                                  {slackConnected ? 'Linked to Workspace' : configStatus?.slack?.configured ? 'Invalid or Expired Token' : 'App Manifest setup required'}
                                </div>
                              </div>
                            </div>
                            {!slackConnected && (
                              <button onClick={() => setActiveTab('slack')} className="px-3 py-1 bg-white text-black text-[10px] font-bold rounded-md uppercase tracking-wider">Configure</button>
                            )}
                            {slackConnected && <CheckCircle2 className="text-white" size={18} />}
                          </div>

                          {/* Google Status */}
                          <div className={`p-4 rounded-xl border flex items-center justify-between ${googleConnected ? 'bg-white/5 border-white/20' : 'bg-white/5 border-white/10'}`}>
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg ${googleConnected ? 'bg-white/20 text-white' : 'bg-white/10 text-white'}`}>
                                <ExternalLink size={20} />
                              </div>
                              <div>
                                <div className="text-sm font-bold">Google API Config</div>
                                <div className="text-[10px] opacity-60">{configStatus?.google.configured ? (googleConnected ? 'Connected' : 'Ready to Connect') : 'Client ID/Secret missing'}</div>
                              </div>
                            </div>
                            {!googleConnected && !configStatus?.google.configured && (
                              <button onClick={() => setActiveTab('google')} className="px-3 py-1 bg-white text-black text-[10px] font-bold rounded-md uppercase tracking-wider">Configure</button>
                            )}
                            {configStatus?.google.configured && !googleConnected && (
                              <button 
                                onClick={handleConnectGoogle}
                                className="px-3 py-1 bg-white text-black text-[10px] font-bold rounded-md uppercase tracking-wider hover:scale-105 transition-all"
                              >
                                Connect Google
                              </button>
                            )}
                            {googleConnected && <CheckCircle2 className="text-white" size={18} />}
                          </div>

                          {/* Tools Status */}
                          <div className={`p-4 rounded-xl border flex items-center justify-between ${allToolsVerified ? 'bg-white/5 border-white/20' : 'bg-white/5 border-white/10'}`}>
                            <div className="flex items-center gap-3">
                              <div className={`p-2 rounded-lg ${allToolsVerified ? 'bg-white/20 text-white' : 'bg-white/10 text-white'}`}>
                                <Cloud size={20} />
                              </div>
                              <div>
                                <div className="text-sm font-bold">External Tools</div>
                                <div className="text-[10px] opacity-60">{allToolsVerified ? 'All systems operational' : 'Weather, Search, and Maps keys'}</div>
                              </div>
                            </div>
                            {allToolsVerified ? (
                              <CheckCircle2 className="text-white" size={18} />
                            ) : (
                              <button onClick={() => setActiveTab('tools')} className="px-3 py-1 bg-white text-black text-[10px] font-bold rounded-md uppercase">Manage</button>
                            )}
                          </div>
                        </>
                      ) : (
                        /* Final Completion UI */
                        <motion.div 
                          initial={{ opacity: 0, scale: 0.9 }}
                          animate={{ opacity: 1, scale: 1 }}
                          className="flex flex-col items-center justify-center py-10 text-center"
                        >
                          <h3 className="text-6xl font-black mb-4 tracking-tighter uppercase">All Done!</h3>
                          <p className="text-lg opacity-60 mb-8 max-w-md">Wingman is fully fueled, encrypted, and ready for take-off.</p>
                          <button 
                            onClick={() => setAuthPromptOpen(false)}
                            className="px-16 py-5 bg-white text-black font-black rounded-2xl hover:scale-105 active:scale-95 transition-all shadow-[0_0_50px_rgba(255,255,255,0.3)] uppercase tracking-[0.2em] text-2xl"
                          >
                            Let's Go!
                          </button>
                        </motion.div>
                      )}
                    </div>
                  </motion.div>
                )}

                {activeTab === 'slack' && (
                  <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                    <div className="mb-6">
                      <h2 className="text-xl font-bold mb-1">Slack Setup Assistant</h2>
                      <p className="text-xs opacity-60">Follow these steps to give Wingman a voice in your workspace.</p>
                    </div>

                    <div className="space-y-6">
                      <div className="p-4 rounded-xl bg-neutral-900 border border-white/10 space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold text-white">
                          <BookOpen size={14} /> 1. Create App via Manifest
                        </div>
                        <p className="text-[11px] opacity-70 leading-relaxed">
                          Go to <a href="https://api.slack.com/apps" target="_blank" className="text-white underline font-bold">Slack Apps</a>, click "Create New App", choose "From an app manifest", and paste this YAML:
                        </p>
                        <div className="relative">
                          <pre className="bg-black border border-white/10 rounded-lg p-3 text-[10px] font-mono text-white/70 overflow-x-auto">
                            {`display_name: Wingman
features:
  bot_user:
    display_name: Wingman
oauth_config:
  scopes:
    bot:
      - channels:history
      - channels:read
      - chat:write
      - users:read...`}
                          </pre>
                          <button
                            onClick={handleCopyManifest}
                            className="absolute top-2 right-2 p-2 bg-neutral-800 rounded-md hover:bg-neutral-700 transition-all shadow-lg"
                          >
                            {copied ? <Check size={14} className="text-white" /> : <Copy size={14} />}
                          </button>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold text-white">
                          <Key size={14} /> 2. Enter Bot OAuth Token
                        </div>
                        <div className="flex gap-2">
                          <input
                            type="password"
                            placeholder="xoxb-..."
                            value={slackToken}
                            onChange={(e) => setSlackToken(e.target.value)}
                            className="flex-1 bg-neutral-900 border border-white/10 rounded-lg px-4 py-2 text-sm font-mono outline-none focus:border-white"
                          />
                          <button
                            disabled={isSubmitting || slackToken === '••••••••'}
                            onClick={handleSaveSlack}
                            className={`px-6 font-bold rounded-lg transition-all flex items-center gap-2 ${
                              slackToken === '••••••••'
                                ? 'bg-white/10 text-white cursor-default'
                                : 'bg-white text-black hover:bg-white/90 shadow-lg'
                            }`}
                          >
                            {isSubmitting ? (
                              <Loader2 size={16} className="animate-spin" />
                            ) : slackToken === '••••••••' ? 'Connected' : 'Save & Connect'}
                          </button>
                        </div>
                        {error && <div className="text-[10px] text-red-500 flex items-center gap-1"><AlertCircle size={10} /> {error}</div>}
                      </div>
                    </div>
                  </motion.div>
                )}

                {activeTab === 'google' && (
                  <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                    <div className="mb-6">
                      <h2 className="text-xl font-bold mb-1">Google Cloud Setup</h2>
                      <p className="text-xs opacity-60">Authorize Wingman to interact with your workspace documents.</p>
                    </div>

                    <div className="space-y-6">
                      {!configStatus?.google.configured && (
                        <div className="p-4 rounded-xl bg-white/5 border border-white/10 flex gap-4">
                          <Info size={32} className="text-white shrink-0" />
                          <div>
                            <h4 className="text-xs font-bold mb-1">Configuration Required</h4>
                            <p className="text-[11px] opacity-70 leading-relaxed mb-2">
                              You must create an OAuth 2.0 Client ID in your Google Cloud Console. Follow our detailed step-by-step guide on GitHub.
                            </p>
                            <a href="https://github.com/PRIME-07/Wingman#google-cloud-setup" target="_blank" className="inline-flex items-center gap-1 text-[10px] font-bold text-white hover:underline">
                              View Setup Guide <ExternalLink size={10} />
                            </a>
                          </div>
                        </div>
                      )}

                      <div className="grid grid-cols-1 gap-4">
                        <SecretInput
                          label="Client ID"
                          placeholder="...apps.googleusercontent.com"
                          value={googleKeys.google_client_id}
                          onChange={(val) => setGoogleKeys({ ...googleKeys, google_client_id: val })}
                        />
                        <SecretInput
                          label="Client Secret"
                          placeholder="GOCSPX-..."
                          value={googleKeys.google_client_secret}
                          onChange={(val) => setGoogleKeys({ ...googleKeys, google_client_secret: val })}
                        />
                        
                        <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20 mb-4">
                          <div className="text-[10px] text-blue-400 font-bold uppercase mb-1">OAuth Redirect URI</div>
                          <div className="flex items-center justify-between gap-2">
                            <code className="text-[10px] bg-black/40 px-2 py-1 rounded select-all break-all">
                              {import.meta.env.VITE_BACKEND_URL ? `http://${import.meta.env.VITE_BACKEND_URL}/api/v1/auth/google/callback` : 'http://localhost:8000/api/v1/auth/google/callback'}
                            </code>
                            <button 
                              onClick={() => {
                                navigator.clipboard.writeText(import.meta.env.VITE_BACKEND_URL ? `http://${import.meta.env.VITE_BACKEND_URL}/api/v1/auth/google/callback` : 'http://localhost:8000/api/v1/auth/google/callback');
                                // Could add a temporary "Copied" tooltip here if we had state for it
                              }}
                              className="p-1 hover:bg-white/10 rounded transition-colors"
                              title="Copy to clipboard"
                            >
                              <Copy size={12} />
                            </button>
                          </div>
                          <div className="text-[9px] text-blue-400/60 mt-2">
                            Add this exact URL to your "Authorized redirect URIs" in the Google Cloud Console.
                          </div>
                        </div>

                        <div className="flex flex-col gap-3">
                          <button
                            disabled={isSubmitting || (configStatus?.google.configured && !!googleConnected && googleKeys.google_client_id === '••••••••' && googleKeys.google_client_secret === '••••••••')}
                            onClick={handleSaveGoogleConfig}
                            className={`w-full py-3 font-bold rounded-xl transition-all flex items-center justify-center gap-2 ${
                              configStatus?.google.configured && googleConnected
                                ? 'bg-green-500/20 text-green-500 border border-green-500/50'
                                : 'bg-white text-black hover:bg-white/90 shadow-lg'
                            }`}
                          >
                            {isSubmitting ? (
                              <Loader2 size={16} className="animate-spin" />
                            ) : (configStatus?.google.configured && !googleConnected) ? 'Authenticate Google' : configStatus?.google.configured ? 'Connected' : 'Save & Connect'}
                          </button>
                          {error && <div className="text-[10px] text-red-500 flex items-center justify-center gap-1"><AlertCircle size={10} /> {error}</div>}
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}

                {activeTab === 'tools' && (
                  <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                    <div className="mb-6">
                      <h2 className="text-xl font-bold mb-1">Toolbox Credentials</h2>
                      <p className="text-xs opacity-60">Unlock specialized capabilities for search, weather, and maps.</p>
                      <div className="mt-4 p-3 rounded-xl border border-white/20 bg-white/5 flex items-start gap-3">
                        <div className="p-1 rounded-full bg-white/10 text-white flex-shrink-0">
                          <Info size={12} />
                        </div>
                        <div className="flex-1">
                          <p className="text-[10px] font-bold text-white mb-2 uppercase tracking-wider">How to get API keys</p>
                          <div className="flex flex-wrap gap-x-4 gap-y-2">
                            <a href="https://home.openweathermap.org/api_keys" target="_blank" className="text-[10px] text-white/40 hover:text-white underline font-bold">OpenWeather</a>
                            <a href="https://tavily.com/" target="_blank" className="text-[10px] text-white/40 hover:text-white underline font-bold">Tavily</a>
                            <a href="https://console.cloud.google.com/google/maps-apis/credentials" target="_blank" className="text-[10px] text-white/40 hover:text-white underline font-bold">Maps</a>
                            <a href="https://console.cloud.google.com/apis/credentials" target="_blank" className="text-[10px] text-white/40 hover:text-white underline font-bold">YouTube</a>
                          </div>
                        </div>
                      </div>
                    </div>

                    <div className="space-y-4">
                      <div className="grid grid-cols-1 gap-4">
                        {[
                          { id: 'weather_api_key', label: 'OpenWeather API Key', icon: Cloud },
                          { id: 'tavily_api_key', label: 'Tavily Search API Key (tvly-...)', icon: Search },
                          { id: 'google_maps_api_key', label: 'Google Maps API Key', icon: Map },
                          { id: 'youtube_api_key', label: 'YouTube API Key', icon: Youtube }
                        ].map((tool) => (
                          <div key={tool.id} className="relative group">
                            <div className="absolute left-3 top-1/2 -translate-y-1/2 p-1.5 rounded-md bg-white/10 text-white group-focus-within:bg-white group-focus-within:text-black transition-all">
                              <tool.icon size={14} />
                            </div>
                            <input
                              type="password"
                              placeholder={tool.label}
                              value={toolKeys[tool.id as keyof typeof toolKeys]}
                              onChange={(e) => setToolKeys({ ...toolKeys, [tool.id]: e.target.value })}
                              className="w-full bg-neutral-900 border border-white/10 rounded-lg pl-12 pr-24 py-3 text-sm font-mono outline-none focus:border-white transition-all"
                            />
                            <button
                              onClick={() => handleVerifySingleTool('tools', tool.id, toolKeys[tool.id as keyof typeof toolKeys])}
                              disabled={verifyingKey === tool.id || !toolKeys[tool.id as keyof typeof toolKeys] || (toolKeys[tool.id as keyof typeof toolKeys] === '••••••••')}
                              className={`absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${
                                (verifiedKeys[tool.id] || toolKeys[tool.id as keyof typeof toolKeys] === '••••••••')
                                  ? 'bg-green-500/20 text-green-500 border border-green-500/50 cursor-default' 
                                  : 'bg-white/10 hover:bg-white text-white hover:text-black disabled:opacity-30 disabled:hover:bg-white/10 disabled:hover:text-white'
                              }`}
                            >
                              {verifyingKey === tool.id ? (
                                <Loader2 size={12} className="animate-spin" />
                              ) : (verifiedKeys[tool.id] || toolKeys[tool.id as keyof typeof toolKeys] === '••••••••') ? (
                                'Connected'
                              ) : (
                                'Verify'
                              )}
                            </button>
                          </div>
                        ))}
                      </div>

                      <div className="space-y-3">
                        <button
                          disabled={!Object.keys(toolKeys).every(k => {
                            const mapping: Record<string, string> = {
                              weather_api_key: 'weather',
                              tavily_api_key: 'search',
                              google_maps_api_key: 'maps',
                              youtube_api_key: 'youtube'
                            };
                            return verifiedKeys[k] || configStatus?.tools[mapping[k] as keyof typeof configStatus.tools];
                          })}
                          onClick={handleSaveTools}
                          className="w-full py-3 bg-white disabled:bg-white/20 disabled:text-white/40 hover:bg-white/90 text-black font-bold rounded-xl transition-all shadow-lg flex items-center justify-center gap-2"
                        >
                          Update Toolbelt
                        </button>
                        {error && <div className="text-[10px] text-red-500 flex items-center justify-center gap-1"><AlertCircle size={10} /> {error}</div>}
                      </div>
                    </div>
                  </motion.div>
                )}



                {activeTab === 'engine' && (
                  <motion.div initial={{ opacity: 0, x: 10 }} animate={{ opacity: 1, x: 0 }}>
                    <div className="mb-6">
                      <h2 className="text-xl font-bold mb-1">LLM Engine Setup</h2>
                      <p className="text-xs opacity-60">The primary brain of Wingman. Stored with AES-256 encryption.</p>
                      <div className="mt-3 flex gap-3">
                        <a href="https://platform.openai.com/api-keys" target="_blank" className="text-[10px] text-white/60 hover:text-white underline font-bold">Get OpenAI Key</a>
                        <a href="https://github.com/PRIME-07/Wingman#llm-engine-setup" target="_blank" className="text-[10px] text-white/60 hover:text-white underline font-bold">Engine Guide</a>
                      </div>
                    </div>

                    <div className="space-y-6">
                      <div className="space-y-2">
                        <label className="text-[10px] font-bold uppercase opacity-40">OpenAI API Key</label>
                        <div className="relative group">
                          <input
                            type="password"
                            placeholder="sk-..."
                            value={engineKeys.openai_api_key}
                            onChange={(e) => setEngineKeys({ openai_api_key: e.target.value })}
                            className="w-full bg-neutral-900 border border-white/10 rounded-lg pl-4 pr-24 py-3 text-sm font-mono outline-none focus:border-white transition-all"
                          />
                          <button
                            onClick={() => handleVerifySingleTool('engine', 'openai_api_key', engineKeys.openai_api_key)}
                            disabled={verifyingKey === 'openai_api_key' || !engineKeys.openai_api_key || engineKeys.openai_api_key === '••••••••'}
                            className={`absolute right-2 top-1/2 -translate-y-1/2 px-3 py-1 rounded-md text-[10px] font-bold uppercase tracking-wider transition-all ${
                              (verifiedKeys['openai_api_key'] || engineKeys.openai_api_key === '••••••••')
                                ? 'bg-green-500/20 text-green-500 border border-green-500/50 cursor-default' 
                                : 'bg-white/10 hover:bg-white text-white hover:text-black disabled:opacity-30 disabled:hover:bg-white/10 disabled:hover:text-white'
                            }`}
                          >
                            {verifyingKey === 'openai_api_key' ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (verifiedKeys['openai_api_key'] || engineKeys.openai_api_key === '••••••••') ? (
                              'Verified'
                            ) : (
                              'Verify'
                            )}
                          </button>
                        </div>
                      </div>

                      <div className="space-y-3">
                        <button
                          disabled={isSubmitting || engineKeys.openai_api_key === '••••••••'}
                          onClick={handleSaveEngine}
                          className={`w-full py-3 font-bold rounded-xl transition-all flex items-center justify-center gap-2 ${
                            engineKeys.openai_api_key === '••••••••'
                              ? 'bg-white/10 text-white cursor-default'
                              : 'bg-white text-black hover:bg-white/90 shadow-lg'
                          }`}
                        >
                          {isSubmitting ? (
                            <Loader2 size={16} className="animate-spin" />
                          ) : engineKeys.openai_api_key === '••••••••' ? 'Engine Ready' : 'Activate Engine'}
                        </button>
                        {error && <div className="text-[10px] text-red-500 flex items-center justify-center gap-1"><AlertCircle size={10} /> {error}</div>}
                      </div>

                      <div className="p-3 rounded-xl border border-white/20 bg-white/5 flex items-start gap-3">
                        <div className="p-1 rounded-full bg-white/10 text-white flex-shrink-0">
                          <Info size={12} />
                        </div>
                        <div className="flex-1">
                          <p className="text-[10px] font-bold text-white mb-2 uppercase tracking-wider">How to get API keys</p>
                          <a href="https://platform.openai.com/api-keys" target="_blank" className="text-[10px] text-white/40 hover:text-white underline font-bold">OpenAI Dashboard</a>
                          <p className="text-[9px] opacity-40 mt-2 italic">Note: Only OpenAI is supported currently.</p>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
