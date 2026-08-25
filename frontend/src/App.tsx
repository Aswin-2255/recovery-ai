import { useState, useEffect } from 'react';
import { Shield, Activity, Database, CheckCircle2, AlertCircle, RefreshCw, Cpu, GitBranch, ArrowRight } from 'lucide-react';

interface HealthData {
  status: string;
  app: string;
  version: string;
  environment: string;
  timestamp: string;
  database: {
    status: string;
    dialect: string;
    mode: string;
    error?: string;
  };
  razorpay_mode: string;
  llm_provider: string;
}

export default function App() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string>('');

  const fetchHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      // Fetch from relative /api/health (proxied by Vite) or fallback to direct port 8000
      const response = await fetch('/api/health').catch(() => fetch('http://127.0.0.1:8000/health'));
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      const data: HealthData = await response.json();
      setHealth(data);
      setLastChecked(new Date().toLocaleTimeString());
    } catch (err: any) {
      setError(err.message || 'Unable to connect to backend server');
      setLastChecked(new Date().toLocaleTimeString());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
  }, []);

  return (
    <div className="min-h-screen bg-[#0B0F19] text-slate-100 flex flex-col justify-between selection:bg-emerald-500/20 selection:text-emerald-300">
      {/* Top Navbar */}
      <header className="border-b border-slate-800/80 bg-slate-900/50 backdrop-blur-md px-6 py-4 sticky top-0 z-50">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-emerald-500 to-teal-400 flex items-center justify-center shadow-lg shadow-emerald-500/20">
              <Shield className="w-5 h-5 text-slate-950 stroke-[2.5]" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h1 className="text-xl font-bold tracking-tight text-white">RecoverAI</h1>
                <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                  Track 3: AI Revenue Recovery
                </span>
              </div>
              <p className="text-xs text-slate-400 font-normal">Razorpay Buildathon 2026</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            <button
              onClick={fetchHealth}
              disabled={loading}
              className="flex items-center space-x-2 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-xs font-medium text-slate-300 transition-all border border-slate-700/60 active:scale-95 disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-emerald-400' : ''}`} />
              <span>Refresh Status</span>
            </button>
            <div className="flex items-center space-x-2 text-xs">
              <span className="relative flex h-2.5 w-2.5">
                <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${health?.status === 'ok' ? 'bg-emerald-400' : 'bg-amber-400'}`}></span>
                <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${health?.status === 'ok' ? 'bg-emerald-500' : 'bg-amber-500'}`}></span>
              </span>
              <span className="text-slate-400 font-mono">
                {health?.status === 'ok' ? 'SYSTEM ONLINE' : loading ? 'CHECKING...' : 'DEGRADED'}
              </span>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex-1 max-w-6xl w-full mx-auto px-6 py-10">
        {/* Hero Section */}
        <div className="text-center max-w-3xl mx-auto mb-12">
          <div className="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-slate-800/60 border border-slate-700/60 text-slate-300 text-xs font-medium mb-4">
            <Activity className="w-3.5 h-3.5 text-emerald-400" />
            <span>Milestone 1 — Project Foundation Active</span>
          </div>
          <h2 className="text-4xl sm:text-5xl font-extrabold tracking-tight text-white mb-4">
            “Detect lost revenue.{' '}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400">
              Recover it safely.
            </span>{' '}
            Prove the impact.”
          </h2>
          <p className="text-slate-400 text-base sm:text-lg leading-relaxed">
            Autonomous, policy-bounded revenue recovery engine engineered to detect failed payments, diagnose root causes, bound interventions, and reconcile recovered revenue with full auditability.
          </p>
        </div>

        {/* Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
          {/* Frontend Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-xl bg-cyan-500/10 border border-cyan-500/20 text-cyan-400">
                <Activity className="w-5 h-5" />
              </div>
              <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="w-3 h-3 mr-1" /> Active
              </span>
            </div>
            <h3 className="text-base font-semibold text-white mb-1">React + Vite Frontend</h3>
            <p className="text-xs text-slate-400 mb-4">TypeScript, Tailwind CSS & Recharts layer ready.</p>
            <div className="text-[11px] font-mono bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/60 text-slate-400">
              Port: <span className="text-emerald-400 font-semibold">5173</span> | HMR Enabled
            </div>
          </div>

          {/* Backend Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
                <Cpu className="w-5 h-5" />
              </div>
              <span className={`inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full ${health ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
                {health ? <CheckCircle2 className="w-3 h-3 mr-1" /> : <AlertCircle className="w-3 h-3 mr-1" />}
                {health ? 'Connected' : 'Connecting...'}
              </span>
            </div>
            <h3 className="text-base font-semibold text-white mb-1">FastAPI Backend</h3>
            <p className="text-xs text-slate-400 mb-4">Pydantic v2, CORS, and REST API foundation.</p>
            <div className="text-[11px] font-mono bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/60 text-slate-400">
              Endpoint: <span className="text-emerald-400 font-semibold">GET /health</span> (v{health?.version || '0.1.0'})
            </div>
          </div>

          {/* Database Card */}
          <div className="bg-slate-900/60 border border-slate-800 rounded-2xl p-6 relative overflow-hidden backdrop-blur-sm">
            <div className="flex items-center justify-between mb-4">
              <div className="p-2.5 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-400">
                <Database className="w-5 h-5" />
              </div>
              <span className="inline-flex items-center text-xs font-semibold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <CheckCircle2 className="w-3 h-3 mr-1" /> {health?.database?.status === 'connected' ? 'Configured' : 'Ready'}
              </span>
            </div>
            <h3 className="text-base font-semibold text-white mb-1">SQLAlchemy ORM</h3>
            <p className="text-xs text-slate-400 mb-4">PostgreSQL schema engine with dev fallback.</p>
            <div className="text-[11px] font-mono bg-slate-950/60 rounded-lg p-2.5 border border-slate-800/60 text-slate-400 truncate">
              Dialect: <span className="text-emerald-400 font-semibold">{health?.database?.dialect || 'postgresql/sqlite'}</span> ({health?.database?.mode || 'ready'})
            </div>
          </div>
        </div>

        {/* Live Diagnostics Terminal Box */}
        <div className="bg-slate-950 border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl">
          <div className="bg-slate-900/90 border-b border-slate-800/80 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className="w-3 h-3 rounded-full bg-red-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-yellow-500/80"></div>
              <div className="w-3 h-3 rounded-full bg-green-500/80"></div>
              <span className="ml-2 text-xs font-mono text-slate-400 font-medium">recoverai-diagnostics.json</span>
            </div>
            <span className="text-[11px] font-mono text-slate-500">Last sync: {lastChecked || 'Initial check'}</span>
          </div>

          <div className="p-5 font-mono text-xs overflow-x-auto text-slate-300 leading-relaxed">
            {loading && !health ? (
              <div className="flex items-center space-x-2 text-slate-500 animate-pulse">
                <span>Pinging backend health endpoint...</span>
              </div>
            ) : error ? (
              <div className="text-red-400 flex items-start space-x-2">
                <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-semibold">Connection Error:</p>
                  <p className="text-slate-400">{error}</p>
                </div>
              </div>
            ) : (
              <pre className="text-emerald-400/90 whitespace-pre-wrap">
                {JSON.stringify(health, null, 2)}
              </pre>
            )}
          </div>
        </div>

        {/* Next Step Banner */}
        <div className="mt-8 p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 flex items-center justify-between text-xs text-slate-400">
          <div className="flex items-center space-x-2">
            <GitBranch className="w-4 h-4 text-emerald-400" />
            <span>Milestone 1 Completed: Project Foundation & Verified Infrastructure</span>
          </div>
          <div className="flex items-center space-x-1 text-slate-500">
            <span>Awaiting Milestone 2 Approval</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 px-6 text-center text-xs text-slate-500">
        RecoverAI &copy; 2026 &bull; Razorpay Buildathon &bull; Track 3: AI Revenue Recovery
      </footer>
    </div>
  );
}
