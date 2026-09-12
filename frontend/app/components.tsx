"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useState } from "react";
import { AlertCircle, Menu, X, UploadCloud, BarChart2, Zap, TrendingUp, HelpCircle, Database, Activity, ShieldCheck, LogOut } from "lucide-react";

export const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
export type Summary = Record<string, any>;
export type UploadResult = { upload_id?: string; valid?: boolean; records?: number; errors?: string[]; warnings?: string[] };

export function useActiveUpload() {
  const [uploadId, setUploadId] = useState("");
  const [ready, setReady] = useState(false);
  useEffect(() => { setUploadId(localStorage.getItem("active_upload_id") ?? ""); setReady(true); }, []);
  function saveUpload(id: string) {
    setUploadId(id);
    if (id) localStorage.setItem("active_upload_id", id);
  }
  return { uploadId, saveUpload, ready };
}

export function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [menuOpen, setMenuOpen] = useState(false);
  const [user, setUser] = useState<any>(null);
  
  useEffect(() => {
    const supabase = createClient();
    supabase.auth.getUser().then(({ data }) => setUser(data?.user));
  }, []);

  const handleLogout = async () => {
    const supabase = createClient();
    await supabase.auth.signOut();
    localStorage.removeItem("energy_upload_id");
    router.push("/login");
    router.refresh();
  };
  
  const links = [
    { href: "/dashboard", label: "Dashboard", icon: <BarChart2 size={18} /> },
    { href: "/upload", label: "Upload Data", icon: <UploadCloud size={18} /> },
    { href: "/my-data", label: "My Datasets", icon: <Database size={18} /> },
    { href: "/forecast", label: "Forecast", icon: <TrendingUp size={18} /> },
    { href: "/analytics", label: "Analytics", icon: <Activity size={18} /> },
    { href: "/smart-grid", label: "Smart Grid", icon: <Zap size={18} /> },
    { href: "/recommendations", label: "Recommendations", icon: <ShieldCheck size={18} /> },
  ];

  return (
    <div className="flex min-h-screen bg-paper font-sans">
      {/* Mobile Overlay */}
      {menuOpen && (
        <div 
          className="fixed inset-0 bg-ink/50 z-40 md:hidden" 
          onClick={() => setMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={`fixed md:sticky top-0 h-screen w-64 bg-brand-dark text-white flex flex-col transition-transform z-50 ${menuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}>
        <div className="p-6 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-brand-accent flex items-center justify-center text-white font-bold text-sm">⚡</div>
            <div>
              <b className="block text-base tracking-tight">EnergySense</b>
              <small className="text-brand-accent/80 text-xs font-medium">Decision Support</small>
            </div>
          </Link>
          <button className="md:hidden text-white/70 hover:text-white transition-colors" onClick={() => setMenuOpen(false)}>
            <X size={20} />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-4 py-2 space-y-1">
          <div className="text-xs font-bold text-white/40 uppercase tracking-wider mb-2 px-4 mt-2">Analysis</div>
          {links.map(({ href, label, icon }) => {
            const isActive = pathname === href.split('?')[0];
            return (
              <Link 
                key={href} 
                href={href}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all ${
                  isActive 
                    ? "bg-brand-accent text-white shadow-sm" 
                    : "text-white/70 hover:bg-white/10 hover:text-white"
                }`}
              >
                <div className={isActive ? "text-white" : "text-white/50"}>{icon}</div>
                {label}
              </Link>
            );
          })}
        </div>

        {user && (
          <div className="p-4 mt-auto border-t border-white/10 bg-black/10">
            <div className="px-4 py-3">
              <span className="block text-xs text-white/50 font-medium uppercase tracking-wider mb-1">Account</span>
              <strong className="block text-sm font-bold truncate">{user.user_metadata?.full_name || 'User'}</strong>
              <span className="block text-xs text-white/70 truncate">{user.email}</span>
            </div>
            <button 
              onClick={handleLogout}
              className="w-full mt-2 text-left px-4 py-2.5 rounded-lg text-sm font-medium text-red-400 hover:bg-white/5 hover:text-red-300 transition-colors flex items-center gap-2"
            >
              <LogOut size={16} />
              Logout
            </button>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0 h-screen overflow-y-auto">
        <div className="md:hidden p-4 border-b border-line bg-white flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded bg-brand-dark flex items-center justify-center text-white font-bold text-xs">⚡</div>
            <span className="font-bold text-brand-dark">EnergySense</span>
          </div>
          <button onClick={() => setMenuOpen(true)} className="p-2 rounded-lg border border-line text-ink">
            <Menu size={20} />
          </button>
        </div>
        
        <div className="p-6 md:p-10 max-w-7xl mx-auto w-full flex-1">
          {children}
        </div>
        
        <footer className="py-6 text-center text-xs text-muted">
          Forecast-based decision support · No live smart-meter connection · No automatic appliance control
        </footer>
      </main>
    </div>
  );
}

export function Header({ eyebrow, title, description, action }: { eyebrow: string; title: string; description: string; action?: React.ReactNode }) {
  return (
    <header className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-10">
      <div>
        <p className="text-xs font-bold tracking-widest text-brand-accent mb-2 uppercase">{eyebrow}</p>
        <h1 className="text-3xl md:text-4xl font-extrabold text-brand-dark tracking-tight mb-2">{title}</h1>
        <p className="text-muted text-base">{description}</p>
      </div>
      {action && <div>{action}</div>}
    </header>
  );
}

export function State({ loading, error, children }: { loading?: boolean; error?: string; children?: React.ReactNode }) {
  if (loading) return (
    <div className="flex items-center justify-center p-12 bg-white rounded-2xl border border-line animate-pulse">
      <div className="flex items-center gap-3 text-muted">
        <div className="w-5 h-5 border-2 border-brand-accent/30 border-t-brand-accent rounded-full animate-spin"></div>
        Loading insights...
      </div>
    </div>
  );
  if (error) return (
    <div className="p-6 bg-red/10 text-red rounded-2xl border border-red/20 flex items-start gap-3">
      <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
      <div>
        <h3 className="font-bold text-sm">Unable to load data</h3>
        <p className="text-sm mt-1 opacity-90">{error}</p>
      </div>
    </div>
  );
  return <>{children}</>;
}

export function Metric({ label, value, suffix, tone = "default", icon }: { label: string; value: any; suffix?: string; tone?: string; icon?: React.ReactNode }) {
  const tones: Record<string, string> = {
    default: "border-t-transparent",
    blue: "border-t-blue",
    amber: "border-t-amber",
    red: "border-t-red",
    green: "border-t-green"
  };
  
  return (
    <article className={`bg-white border border-line rounded-2xl p-6 shadow-sm border-t-4 ${tones[tone] || tones.default}`}>
      {icon}
      <span className="block text-sm text-muted font-medium mb-2">{label}</span>
      <strong className="block text-3xl font-bold tracking-tight text-ink">{value ?? "—"}</strong>
      {suffix && <small className="block text-sm text-muted mt-1">{suffix}</small>}
    </article>
  );
}

import { createClient } from "@/utils/supabase/client";

export function useFetch<T>(path: string, fallback: T) {
  const [data, setData] = useState<T>(fallback);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => { 
    let alive = true; 
    setLoading(true);
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!alive) return;
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      fetch(`${API}${path}`, { headers })
        .then(r => { 
          if (!r.ok) throw new Error("Unable to load this analysis."); 
          return r.json(); 
        })
        .then(value => alive && setData(value))
        .catch(e => alive && setError(e instanceof Error ? e.message : "Unable to load this analysis."))
        .finally(() => alive && setLoading(false)); 
    });
    return () => { alive = false; }; 
  }, [path]);
  return { data, loading, error };
}

export async function postJson<T>(path: string): Promise<T> {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const headers: Record<string, string> = {};
  if (session?.access_token) {
    headers["Authorization"] = `Bearer ${session.access_token}`;
  }
  
  const response = await fetch(`${API}${path}`, { method: "POST", headers });
  const result = await response.json();
  if (!response.ok) throw new Error(result.detail ?? "Request failed.");
  return result;
}

export function DataTable({ rows }: { rows: any[] }) {
  if (!rows.length) return <p className="p-8 text-center text-muted bg-paper rounded-xl border border-line">No backend records are available for this view.</p>;
  const columns = Object.keys(rows[0]).slice(0, 5);
  return (
    <div className="overflow-x-auto rounded-xl border border-line bg-white shadow-sm">
      <table className="w-full text-left text-sm whitespace-nowrap">
        <thead className="bg-paper border-b border-line text-muted">
          <tr>
            {columns.map(c => <th key={c} className="px-6 py-4 font-semibold capitalize">{c.replaceAll("_", " ")}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.slice(0, 50).map((row, i) => (
            <tr key={i} className="hover:bg-paper/50 transition-colors">
              {columns.map(c => (
                <td key={c} className="px-6 py-4">
                  {typeof row[c] === "number" ? row[c].toFixed?.(2) ?? row[c] : String(row[c] ?? "—")}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function useUserAnalysis(horizon: number = 24) {
  const { uploadId } = useActiveUpload();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!alive) return;
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }
      
      const url = uploadId 
        ? `${API}/api/forecast/user?upload_id=${encodeURIComponent(uploadId)}&horizon=${horizon}` 
        : `${API}/api/forecast/user?horizon=${horizon}`;
        
      fetch(url, { method: "POST", headers })
        .then(async response => {
          const result = await response.json();
          if (!response.ok) throw new Error(result.detail ?? result.message ?? "Unable to load uploaded analysis.");
          if (alive) setData(result);
        })
        .catch(err => {
          if (alive) setError(err.message);
        })
        .finally(() => {
          if (alive) setLoading(false);
        });
    });
    return () => { alive = false; };
  }, [uploadId]);
  return { data, loading, error };
}

export function useUserPeriods() {
  const [periods, setPeriods] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  useEffect(() => {
    let alive = true;
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!alive) return;
      if (!session) {
        setLoading(false);
        setError("Not authenticated");
        return;
      }
      fetch(`${API}/api/user/periods`, { 
        headers: { "Authorization": `Bearer ${session.access_token}` } 
      })
      .then(async res => {
        const result = await res.json();
        if (!res.ok) throw new Error(result.detail ?? "Failed to load periods");
        if (alive) setPeriods(result);
      })
      .catch(err => { if (alive) setError(err.message); })
      .finally(() => { if (alive) setLoading(false); });
    });
    return () => { alive = false; };
  }, []);
  return { periods, loading, error };
}

export function useUserDashboard(period?: string | null) {
  const [dashboard, setDashboard] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  
  useEffect(() => {
    let alive = true;
    setLoading(true);
    setError("");
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!alive) return;
      if (!session) {
        setLoading(false);
        setError("Not authenticated");
        return;
      }
      
      const headers = { "Authorization": `Bearer ${session.access_token}` };
      const url = period 
        ? `${API}/api/user/dashboard?period=${encodeURIComponent(period)}` 
        : `${API}/api/user/dashboard`;
        
      fetch(url, { headers })
      .then(async res => {
        const result = await res.json();
        // If the requested period doesn't exist (stale URL), silently retry
        // with no period so the backend picks the latest automatically
        if (res.status === 404 && period) {
          return fetch(`${API}/api/user/dashboard`, { headers })
            .then(async r2 => {
              const r2data = await r2.json();
              if (!r2.ok) throw new Error(r2data.detail ?? "No data available");
              if (alive) setDashboard(r2data);
            });
        }
        if (!res.ok) throw new Error(result.detail ?? "Failed to load dashboard");
        if (alive) setDashboard(result);
      })
      .catch(err => { if (alive) setError(err.message); })
      .finally(() => { if (alive) setLoading(false); });
    });
    return () => { alive = false; };
  }, [period]);
  
  return { dashboard, loading, error };
}



export function CostBadge({ source }: { source: string }) {
  if (source === 'actual_bill') {
    return <span className="bg-green-100 text-green-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">ACTUAL BILL</span>;
  }
  if (source === 'estimated') {
    return <span className="bg-yellow-100 text-yellow-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider" title="Based on configured energy rate.">ESTIMATED</span>;
  }
  if (source === 'forecast') {
    return <span className="bg-purple-100 text-purple-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">FORECAST ESTIMATE</span>;
  }
  if (source === 'simulation') {
    return <span className="bg-blue-100 text-blue-800 text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-wider">SIMULATION</span>;
  }
  return null;
}

export function useUserCostAnalytics() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  
  useEffect(() => {
    let alive = true;
    setLoading(true);
    const supabase = createClient();
    supabase.auth.getSession().then(({ data: { session } }) => {
      if (!alive) return;
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers['Authorization'] = `Bearer ${session.access_token}`;
      }
      fetch(`${API}/api/user/analytics/cost`, { headers })
        .then(res => res.json())
        .then(res => { if (alive) { setData(res); setLoading(false); } })
        .catch(err => { if (alive) { setError(err.message); setLoading(false); } });
    });
    return () => { alive = false; };
  }, []);
  
  return { data, loading, error };
}
