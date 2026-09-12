"use client";
import { useEffect, useState } from "react";
import { Header, Shell, State, useActiveUpload, API, CostBadge } from "../components";
import { TrendingUp, ShieldCheck, AlertTriangle, Database, HelpCircle } from "lucide-react";
import { ForecastChart } from "../components/charts";

export default function ForecastPage() {
  const { uploadId } = useActiveUpload();
  const [horizon, setHorizon] = useState<1 | 24>(24);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [data, setData] = useState<any>(null);

  useEffect(() => {
    if (!uploadId) return;
    let alive = true;
    setLoading(true);
    setError("");
    const loadData = async () => {
      try {
        const { createClient } = await import("@/utils/supabase/client");
        const supabase = createClient();
        const { data: { session } } = await supabase.auth.getSession();
        const headers: Record<string, string> = {};
        if (session?.access_token) {
          headers["Authorization"] = `Bearer ${session.access_token}`;
        }
        
        const response = await fetch(`${API}/api/forecast/user?upload_id=${encodeURIComponent(uploadId)}&horizon=${horizon}`, { method: "POST", headers });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail ?? result.message ?? "Unable to load forecast.");
        if (result.status === "insufficient_history") throw new Error(result.message);
        if (alive) setData(result);
      } catch (err: any) {
        if (alive) setError(err.message || "Unable to load forecast.");
      } finally {
        if (alive) setLoading(false);
      }
    };
    loadData();
    return () => { alive = false; };
  }, [uploadId, horizon]);

  if (!uploadId) {
    return (
      <Shell>
        <Header eyebrow="FORECASTING" title="Predicted household demand" description="Explore future consumption based on historical patterns." />
        <div className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm max-w-2xl mx-auto mt-8">
          <TrendingUp className="w-12 h-12 text-muted mx-auto mb-4" />
          <h2 className="text-xl font-bold text-brand-dark mb-2">No forecast available.</h2>
          <p className="text-muted">Analyze a household dataset first to generate a personalized prediction.</p>
        </div>
      </Shell>
    );
  }

  const isPeak = data?.forecast && data.forecast[0] && data.forecast[0].predicted_consumption > (data.peak_threshold ?? Infinity);

  return (
    <Shell>
      <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-8">
        <div>
          <p className="text-xs font-bold tracking-widest text-brand-accent mb-2 uppercase">FORECASTING</p>
          <h1 className="text-3xl md:text-4xl font-extrabold text-brand-dark tracking-tight mb-2">Predicted household demand</h1>
          <p className="text-muted text-base">Explore future consumption based on historical patterns.</p>
        </div>
        
        {/* Horizon Controls */}
        <div className="bg-paper p-1 rounded-xl border border-line inline-flex">
          <button 
            onClick={() => setHorizon(1)}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-colors ${horizon === 1 ? 'bg-white shadow-sm text-brand-dark' : 'text-muted hover:text-ink'}`}
          >
            1 Hour
          </button>
          <button 
            onClick={() => setHorizon(24)}
            className={`px-6 py-2 rounded-lg text-sm font-bold transition-colors ${horizon === 24 ? 'bg-white shadow-sm text-brand-dark' : 'text-muted hover:text-ink'}`}
          >
            24 Hours
          </button>
        </div>
      </div>

      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue/10 text-blue font-bold text-[10px] tracking-wider mb-8 border border-blue/20">
        UPLOADED HOUSEHOLD DATA · FORECAST
      </div>

      <State loading={loading} error={error}>
        {data && data.status === "complete" && (
          <div className="grid lg:grid-cols-3 gap-6">
            
            {/* Main Visual */}
            <div className="lg:col-span-2 bg-white border border-line rounded-3xl p-6 shadow-sm flex flex-col">
              <h2 className="text-xl font-bold text-ink mb-6">Demand trajectory</h2>
              <div className="flex-1 min-h-[350px]">
                <ForecastChart 
                  historical={data.historical ? data.historical.slice(-168) : []} 
                  forecast={data.forecast || []} 
                  threshold={data.peak_threshold} 
                />
              </div>
            </div>

            {/* Right Column: Prediction & Model */}
            <div className="flex flex-col gap-6">
              
              {/* Prediction Card */}
              <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <h3 className="text-sm font-bold text-muted mb-4 uppercase tracking-widest">Next predicted demand</h3>
                <div className="flex items-baseline gap-2 mb-2">
                  <span className="text-5xl font-extrabold text-blue tracking-tight">
                    {data.forecast?.[0]?.predicted_consumption?.toFixed(2) ?? "—"}
                  </span>
                  <span className="text-xl font-bold text-muted">kWh</span>
                </div>
                <p className="text-sm text-ink bg-paper px-3 py-1.5 rounded-lg inline-block border border-line mb-6 font-medium">
                  {data.forecast?.[0]?.timestamp ?? "Unknown time"}
                </p>
                
                <div className="w-full bg-paper p-4 rounded-xl border border-line">
                  <div className="flex justify-between text-xs font-bold mb-2">
                    <span className="text-muted">Peak threshold</span>
                    <span className="text-ink">{data.peak_threshold?.toFixed(2)} kWh</span>
                  </div>
                  <div className="h-2 w-full bg-line rounded-full overflow-hidden relative mb-3">
                    <div 
                      className={`absolute top-0 left-0 h-full rounded-full ${isPeak ? 'bg-red' : 'bg-green'}`} 
                      style={{ width: `${Math.min(100, (data.forecast[0].predicted_consumption / Math.max(0.1, data.peak_threshold)) * 100)}%` }}
                    ></div>
                  </div>
                  <div className={`text-xs font-bold flex items-center gap-1 ${isPeak ? 'text-red' : 'text-green'}`}>
                    {isPeak ? <AlertTriangle size={14}/> : <ShieldCheck size={14}/>}
                    {isPeak ? "ABOVE THRESHOLD" : "BELOW THRESHOLD"}
                  </div>
                </div>
              </div>

              {/* Interpretation */}
              <div className="bg-blue/5 border border-blue/20 rounded-3xl p-6">
                <h3 className="font-bold text-blue mb-2 flex items-center gap-2"><HelpCircle size={18}/> What does this mean?</h3>
                <p className="text-sm text-blue/80 leading-relaxed">
                  Your next predicted consumption of {data.forecast?.[0]?.predicted_consumption?.toFixed(2)} kWh is 
                  <strong> {isPeak ? 'higher' : 'lower'} </strong> 
                  than your historical household peak threshold. {isPeak ? 'Consider shifting heavy appliance usage.' : 'No immediate load-shifting action is required.'}
                </p>
              </div>

              {/* Model Info */}
              <div className="bg-paper border border-line rounded-3xl p-6">
                <h3 className="text-sm font-bold text-muted mb-4 uppercase tracking-widest flex items-center gap-2"><Database size={16}/> Forecast Model</h3>
                <div className="flex items-center justify-between mb-2">
                  <strong className="text-ink text-lg">{data.model ?? "XGBoost"}</strong>
                  <span className="text-xs font-bold bg-white border border-line px-2 py-1 rounded-md">{horizon}-hour production</span>
                </div>
                <p className="text-xs text-muted leading-relaxed">
                  Prediction generated using the project's trained production forecasting model, personalized to your historical baseline.
                </p>
              </div>

            </div>
          </div>
        )}
      </State>
    </Shell>
  );
}
