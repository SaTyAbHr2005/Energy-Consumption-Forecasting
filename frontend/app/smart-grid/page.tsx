"use client";
import { Header, Metric, Shell, State, useActiveUpload, useUserAnalysis, useFetch, CostBadge } from "../components";
import { ForecastChart, SeverityDonutChart, SimpleBarChart } from "../components/charts";
import { AlertTriangle, Clock, Zap, IndianRupee, PieChart, Info, ShieldCheck } from "lucide-react";

export default function SmartGridPage() {
  const { uploadId } = useActiveUpload();
  const { data: userAnalysis, loading: userLoading, error: userError } = useUserAnalysis();
  
  // Also fetch global sensitivity if available
  const sensitivity = useFetch<any[]>("/api/smart-grid/sensitivity", []);

  if (!uploadId) {
    return (
      <Shell>
        <Header eyebrow="SMART GRID" title="Demand & Load Shifting" description="Identify peak periods and optimization opportunities." />
        <div className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm max-w-2xl mx-auto mt-8">
          <Zap className="w-12 h-12 text-muted mx-auto mb-4" />
          <h2 className="text-xl font-bold text-brand-dark mb-2">No smart-grid analysis available.</h2>
          <p className="text-muted">Upload a CSV dataset to simulate peak detection and TOU pricing.</p>
        </div>
      </Shell>
    );
  }

  const smartGrid = userAnalysis?.smart_grid;
  const isReady = !!smartGrid;

  // TOU cost comparison data
  const touChartData = isReady ? [
    { name: "Baseline Cost", cost: smartGrid.tou_baseline_cost },
    { name: "Optimized Cost", cost: Math.max(0, smartGrid.tou_baseline_cost - smartGrid.potential_savings) }
  ] : [];

  return (
    <Shell>
      <Header 
        eyebrow="SMART GRID" 
        title="Demand & Load Shifting" 
        description="Identify peak periods and simulation-based optimization opportunities." 
      />

      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber/10 text-amber font-bold text-[10px] tracking-wider mb-8 border border-amber/20">
        UPLOADED HOUSEHOLD DATA · FORECAST · SIMULATION
      </div>

      <State loading={userLoading} error={userError}>
        {isReady && (
          <div className="flex flex-col gap-8">
            
            {/* Peak Demand Section */}
            <section>
              <h2 className="text-xl font-bold text-ink mb-4 flex items-center gap-2"><ActivityIcon/> Peak Demand Detection</h2>
              <div className="grid lg:grid-cols-4 gap-6 mb-6">
                <Metric label="Peak Periods" value={smartGrid.predicted_peak_count} tone={smartGrid.predicted_peak_count > 0 ? "red" : "green"} />
                <Metric label="Peak Threshold" value={smartGrid.peak_threshold?.toFixed(2)} suffix="kWh" />
                <Metric label="Shiftable Energy" value={smartGrid.total_shiftable_energy?.toFixed(2)} suffix="kWh" tone="blue" />
                <Metric label="Max Predicted" value={smartGrid.highest_predicted_demand?.toFixed(2)} suffix="kWh" tone="amber" />
              </div>

              <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <h3 className="text-sm font-bold text-muted mb-6 uppercase tracking-wider">Predicted demand vs threshold</h3>
                <div className="h-[350px]">
                  <ForecastChart 
                    historical={userAnalysis.historical_series?.slice(-48) || []}
                    forecast={userAnalysis.forecast || []}
                    threshold={smartGrid.peak_threshold}
                  />
                </div>
              </div>
            </section>

            <div className="grid lg:grid-cols-3 gap-6">
              {/* Demand Severity */}
              <section className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <h2 className="text-lg font-bold text-ink mb-6 flex items-center gap-2"><PieChart size={18} className="text-blue"/> Demand Severity</h2>
                <SeverityDonutChart data={smartGrid.demand_severity || {}} />
                <div className="mt-4 text-center">
                  <p className="text-xs text-muted">Distribution of demand states across the forecast horizon.</p>
                </div>
              </section>

              {/* Peak Events List */}
              <section className="lg:col-span-2 bg-white border border-line rounded-3xl p-6 shadow-sm flex flex-col">
                <h2 className="text-lg font-bold text-ink mb-6 flex items-center gap-2"><AlertTriangle size={18} className="text-red"/> Predicted Peak Events</h2>
                
                {smartGrid.peak_demand_forecast && smartGrid.peak_demand_forecast.filter((p:any) => p.is_peak).length > 0 ? (
                  <div className="flex-1 overflow-y-auto max-h-[300px] pr-2 space-y-3">
                    {smartGrid.peak_demand_forecast.filter((p:any) => p.is_peak).map((p: any, i: number) => (
                      <div key={i} className="flex items-center justify-between p-4 bg-red/5 border border-red/10 rounded-xl">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-lg bg-red/10 text-red flex items-center justify-center font-bold">
                            <Clock size={18} />
                          </div>
                          <div>
                            <p className="font-bold text-ink text-sm">{p.timestamp}</p>
                            <p className="text-xs text-muted">Exceeds threshold by {(p.predicted - smartGrid.peak_threshold).toFixed(2)} kWh</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="font-bold text-red text-lg">{p.predicted?.toFixed(2)} <span className="text-sm font-normal">kWh</span></p>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-red bg-red/10 px-2 py-0.5 rounded-full">{p.demand_level}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex-1 flex flex-col items-center justify-center text-center p-8 border-2 border-dashed border-line rounded-xl bg-paper">
                    <ShieldCheck className="w-10 h-10 text-green mb-3" />
                    <p className="font-bold text-ink mb-1">No peak periods predicted</p>
                    <p className="text-sm text-muted">Demand is expected to remain below threshold.</p>
                  </div>
                )}
              </section>
            </div>

            {/* TOU Simulation */}
            <section className="bg-white border border-line rounded-3xl p-6 shadow-sm">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 mb-8">
                <div>
                  <div className="flex items-center gap-2 mb-1"><h2 className="text-xl font-bold text-ink flex items-center gap-2"><IndianRupee size={20} className="text-green"/> TOU Pricing Savings</h2><CostBadge source="simulation" /></div>
                  <p className="text-sm text-muted mt-1">Illustrative simulation of potential cost savings by shifting flexible loads.</p>
                </div>
                <div className="text-right">
                  <span className="block text-2xl font-bold text-green">₹ {smartGrid.potential_savings?.toFixed(2)}</span>
                  <span className="text-xs font-bold text-muted uppercase tracking-wider">Potential Savings</span>
                </div>
              </div>

              <div className="grid md:grid-cols-2 gap-8">
                <div>
                  <div className="flex gap-4 mb-6">
                    <div className="flex-1 p-4 bg-paper rounded-xl border border-line text-center">
                      <span className="block text-xs font-bold text-muted mb-1">OFF-PEAK</span>
                      <strong className="text-lg text-ink">₹3/kWh</strong>
                    </div>
                    <div className="flex-1 p-4 bg-paper rounded-xl border border-line text-center">
                      <span className="block text-xs font-bold text-muted mb-1">NORMAL</span>
                      <strong className="text-lg text-ink">₹6/kWh</strong>
                    </div>
                    <div className="flex-1 p-4 bg-paper rounded-xl border border-line text-center">
                      <span className="block text-xs font-bold text-muted mb-1 text-red">PEAK</span>
                      <strong className="text-lg text-red">₹10/kWh</strong>
                    </div>
                  </div>
                  <div className="bg-blue/5 p-4 rounded-xl border border-blue/20 flex gap-3 text-sm text-blue/80">
                    <Info size={18} className="shrink-0 mt-0.5" />
                    <p>The system simulates shifting the highest flexible consumption from Peak pricing tiers into Off-Peak tiers to calculate these savings.</p>
                  </div>
                </div>

                <div className="h-[200px]">
                  <SimpleBarChart data={touChartData} xKey="name" yKey="cost" color="#138a68" />
                </div>
              </div>
            </section>

          </div>
        )}
      </State>
    </Shell>
  );
}

function ActivityIcon() {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-brand-accent"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>;
}
