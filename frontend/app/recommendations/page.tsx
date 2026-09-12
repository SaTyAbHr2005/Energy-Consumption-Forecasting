"use client";
import { Header, Shell, State, useActiveUpload, useUserAnalysis } from "../components";
import { HelpCircle, AlertTriangle, Lightbulb, Zap, TrendingDown, ArrowRight, ShieldCheck, Clock } from "lucide-react";
import { useState } from "react";

export default function RecommendationsPage() {
  const { uploadId } = useActiveUpload();
  const { data: userAnalysis, loading, error } = useUserAnalysis();

  if (!uploadId) {
    return (
      <Shell>
        <Header eyebrow="RECOMMENDATIONS" title="Energy actions" description="Personalized recommendations based on your consumption data." />
        <div className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm max-w-2xl mx-auto mt-8">
          <Lightbulb className="w-12 h-12 text-muted mx-auto mb-4" />
          <h2 className="text-xl font-bold text-brand-dark mb-2">No recommendations available.</h2>
          <p className="text-muted">Analyze a household dataset first to generate actionable insights.</p>
        </div>
      </Shell>
    );
  }

  const smartGrid = userAnalysis?.smart_grid;
  const isReady = !!smartGrid;
  const recommendations = smartGrid?.recommendations || [];
  const peakCount = smartGrid?.predicted_peak_count || 0;

  return (
    <Shell>
      <Header 
        eyebrow="RECOMMENDATIONS" 
        title="Energy actions" 
        description="What you can do with these insights based on your forecast and historical patterns." 
      />

      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green/10 text-green font-bold text-[10px] tracking-wider mb-8 border border-green/20">
        UPLOADED HOUSEHOLD DATA · FORECAST · SIMULATION
      </div>

      <State loading={loading} error={error}>
        {isReady && (
          <div className="flex flex-col gap-8">
            
            {/* Summary Row */}
            <section className="grid sm:grid-cols-2 gap-6">
              <div className="bg-brand-dark text-white rounded-3xl p-8 shadow-sm flex items-center justify-between">
                <div>
                  <span className="block text-white/70 text-sm font-bold uppercase tracking-wider mb-1">Recommended Actions</span>
                  <strong className="text-4xl font-extrabold">{recommendations.length}</strong>
                </div>
                <div className="w-16 h-16 bg-white/10 rounded-full flex items-center justify-center">
                  <Lightbulb size={32} className="text-brand-accent" />
                </div>
              </div>

              <div className="bg-white border border-line rounded-3xl p-8 shadow-sm flex items-center justify-between">
                <div>
                  <span className="block text-muted text-sm font-bold uppercase tracking-wider mb-1">Peak Periods Identified</span>
                  <strong className={`text-4xl font-extrabold ${peakCount > 0 ? 'text-red' : 'text-green'}`}>{peakCount}</strong>
                </div>
                <div className={`w-16 h-16 rounded-full flex items-center justify-center ${peakCount > 0 ? 'bg-red/10 text-red' : 'bg-green/10 text-green'}`}>
                  {peakCount > 0 ? <AlertTriangle size={32} /> : <ShieldCheck size={32} />}
                </div>
              </div>
            </section>

            {/* Recommendations List */}
            <section className="space-y-6">
              {recommendations.length === 0 ? (
                <div className="bg-white p-12 text-center border border-line rounded-3xl">
                  <ShieldCheck size={48} className="mx-auto text-green mb-4" />
                  <h3 className="text-xl font-bold mb-2">Your consumption is highly optimized</h3>
                  <p className="text-muted">No high-priority recommendations were generated for this period.</p>
                </div>
              ) : (
                recommendations.map((rec: any, idx: number) => (
                  <RecommendationCard key={idx} rec={rec} />
                ))
              )}
            </section>
            
          </div>
        )}
      </State>
    </Shell>
  );
}

function RecommendationCard({ rec }: { rec: any }) {
  const [expanded, setExpanded] = useState(false);

  const getPriorityColors = (priority: string) => {
    const p = priority?.toLowerCase() || '';
    if (p.includes('critical')) return 'bg-red text-white border-red';
    if (p.includes('high')) return 'bg-amber text-white border-amber';
    if (p.includes('medium')) return 'bg-blue text-white border-blue';
    return 'bg-paper text-ink border-line';
  };

  const getPriorityIcon = (priority: string) => {
    const p = priority?.toLowerCase() || '';
    if (p.includes('critical') || p.includes('high')) return <AlertTriangle size={20} />;
    if (p.includes('medium')) return <TrendingDown size={20} />;
    return <Zap size={20} />;
  };

  return (
    <article className="bg-white border border-line hover:border-brand-accent/50 rounded-3xl overflow-hidden transition-all shadow-sm">
      <div 
        className="p-6 md:p-8 cursor-pointer flex flex-col md:flex-row gap-6 md:items-start"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-3 mb-4">
            <span className={`px-3 py-1 text-[10px] font-bold uppercase tracking-wider rounded-md border flex items-center gap-1.5 ${getPriorityColors(rec.priority)}`}>
              {getPriorityIcon(rec.priority)}
              {rec.priority || 'NORMAL'} PRIORITY
            </span>
            <span className="text-sm text-muted font-medium bg-paper px-3 py-1 rounded-md border border-line capitalize">
              {rec.category?.replace(/_/g, ' ') || 'Optimization'}
            </span>
          </div>
          
          <h3 className="text-xl font-bold text-ink mb-2 leading-tight">{rec.action}</h3>
          
          {expanded ? (
            <div className="mt-6 grid md:grid-cols-2 gap-6 animate-in slide-in-from-top-2 fade-in duration-200">
              <div className="bg-blue/5 border border-blue/10 p-5 rounded-2xl">
                <h4 className="text-sm font-bold text-blue mb-2 flex items-center gap-2"><HelpCircle size={16}/> Why this matters</h4>
                <p className="text-sm text-blue/80 leading-relaxed">{rec.reason}</p>
              </div>
              <div className="bg-paper border border-line p-5 rounded-2xl">
                <h4 className="text-sm font-bold text-ink mb-2 flex items-center gap-2"><ActivityIcon/> Supporting signal</h4>
                <div className="text-sm text-muted">
                  <ul className="space-y-2">
                    {Object.entries(rec.supporting_data || {}).map(([key, value]) => (
                      <li key={key} className="flex justify-between items-center border-b border-line pb-2 last:border-0 last:pb-0">
                        <span className="capitalize">{key.replace(/_/g, ' ')}</span>
                        <strong className="text-ink text-right">{typeof value === 'number' ? value.toFixed(2) : String(value)}</strong>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-muted line-clamp-1 mt-2 text-sm">{rec.reason}</p>
          )}
        </div>
        
        <div className="flex items-center justify-end text-brand-accent font-bold text-sm shrink-0 md:mt-2">
          {expanded ? 'Show less' : 'Read more'} <ArrowRight size={16} className={`ml-1 transition-transform ${expanded ? '-rotate-90' : ''}`} />
        </div>
      </div>
    </article>
  );
}

function ActivityIcon() {
  return <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-accent"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>;
}
