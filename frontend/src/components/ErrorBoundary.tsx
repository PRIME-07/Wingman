import { Component } from 'react';
import type { ErrorInfo, ReactNode } from 'react';
import { AlertTriangle, RefreshCw, Home } from 'lucide-react';

interface Props {
  children?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Uncaught error:", error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div className="w-full h-screen flex items-center justify-center bg-white dark:bg-[#000000] p-6 font-sans">
          <div className="max-w-md w-full p-8 rounded-3xl bg-mono-50 dark:bg-mono-900/40 border border-mono-200 dark:border-mono-800 shadow-2xl text-center">
            <div className="w-16 h-16 rounded-2xl bg-red-500/10 text-red-500 flex items-center justify-center mx-auto mb-6">
              <AlertTriangle size={32} />
            </div>
            
            <h1 className="text-xl font-black text-mono-900 dark:text-white mb-2 uppercase tracking-tight">System Fault Detected</h1>
            <p className="text-sm text-mono-500 dark:text-mono-400 mb-8 leading-relaxed">
              The front-end runtime encountered an unexpected exception in the logic core.
            </p>

            <div className="bg-white dark:bg-black p-4 rounded-xl border border-mono-200 dark:border-mono-900 mb-8 text-left overflow-hidden">
              <p className="text-[10px] font-mono text-red-500 dark:text-red-400 break-all leading-tight">
                {this.state.error?.toString()}
              </p>
            </div>

            <div className="flex flex-col gap-3">
              <button
                onClick={() => window.location.reload()}
                className="w-full py-3 bg-mono-900 dark:bg-white text-white dark:text-black font-bold rounded-xl flex items-center justify-center gap-2 hover:scale-[1.02] active:scale-[0.98] transition-all"
              >
                <RefreshCw size={16} />
                <span>Restart Session</span>
              </button>
              
              <button
                onClick={() => {
                  localStorage.removeItem('wingman-active-tab');
                  window.location.href = '/';
                }}
                className="w-full py-3 bg-white dark:bg-mono-800 text-mono-900 dark:text-white border border-mono-200 dark:border-mono-700 font-bold rounded-xl flex items-center justify-center gap-2 hover:bg-mono-50 dark:hover:bg-mono-700 transition-all"
              >
                <Home size={16} />
                <span>Return to Base</span>
              </button>
            </div>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
