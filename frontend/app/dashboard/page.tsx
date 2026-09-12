"use client";

import Link from "next/link";
import { useSearchParams, useRouter } from "next/navigation";
import { useEffect } from "react";
import { Header, Shell, State, useUserDashboard, useUserPeriods, Metric, CostBadge } from "../components";
import { ArrowRight, BarChart2, TrendingUp, Calendar, HelpCircle, Activity, Zap } from "lucide-react";
import { ConsumptionAreaChart, SimpleBarChart } from "../components/charts";

import { Suspense } from "react";

function DashboardContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const period = searchParams?.get("period") || null;
  
  const { periods, loading: periodsLoading, error: periodsError } = useUserPeriods();

  const availablePeriods = periods?.periods || [];
  const availableYears = periods?.years || [];
  const latestPeriod = periods?.latest_period;

  // If the period in the URL is stale/not in the available list, silently redirect to latest
  const allKnownPeriods = [...availablePeriods, ...availableYears];
  const periodIsInvalid = !periodsLoading && period && allKnownPeriods.length > 0 && !allKnownPeriods.includes(period);

  useEffect(() => {
    if (periodIsInvalid && latestPeriod) {
      router.replace(`/dashboard?period=${latestPeriod}`);
    }
  }, [periodIsInvalid, latestPeriod, router]);

  // Use the URL period only if it's valid; otherwise let the backend pick the latest
  const effectivePeriod = periodIsInvalid ? null : period;
  const { dashboard, loading: dashboardLoading, error: dashboardError } = useUserDashboard(effectivePeriod);

  // The active period we are actually viewing
  const activePeriod = period || latestPeriod;
  const isYearView = dashboard?.is_year;

  // Render empty state if the user literally has no data at all
  if (!periodsLoading && !dashboardLoading && availablePeriods.length === 0) {
    return (
      <Shell>
        <Header 
          eyebrow="ENERGY OVERVIEW" 
          title="Your household energy at a glance" 
          description="Household consumption insights and historical energy patterns." 
        />
        <section className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm mt-8 max-w-2xl mx-auto">
          <h2 className="text-2xl font-bold text-brand-dark mb-4">No household data yet.</h2>
          <p className="text-muted mb-8 text-lg">Upload your electricity consumption CSV to start building your personalized energy analysis.</p>
          <Link href="/upload" className="inline-flex items-center gap-2 bg-brand-accent hover:bg-green text-white px-8 py-3 rounded-full text-base font-bold transition-all shadow-md hover:shadow-lg">
            Upload Data
            <ArrowRight size={18} />
          </Link>
        </section>
      </Shell>
    );
  }

  return (
    <Shell>
      <Header 
        eyebrow="ENERGY OVERVIEW" 
        title="Your household energy at a glance" 
        description="Household consumption insights and historical energy patterns." 
      />

      <State loading={periodsLoading || dashboardLoading} error={periodsError || dashboardError}>
        {dashboard && (
          <>
            {/* Period Selector Header */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-8 bg-paper p-4 rounded-2xl border border-line">
              <div className="flex items-center gap-4">
                <span className="text-xs font-bold text-muted uppercase tracking-wider">Time Period</span>
                <select 
                  className="bg-white border border-line rounded-lg px-4 py-2 font-bold text-ink shadow-sm"
                  value={activePeriod || ""}
                  onChange={(e) => router.push(`/dashboard?period=${e.target.value}`)}
                >
                  <optgroup label="Monthly View">
                    {availablePeriods.map((p: string) => (
                      <option key={p} value={p}>
                        {p}
                        {p === latestPeriod ? " (Latest)" : ""}
                      </option>
                    ))}
                  </optgroup>
                  <optgroup label="Yearly View">
                    {availableYears.map((y: string) => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </optgroup>
                </select>
              </div>
              
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-accent/10 text-brand-accent font-bold text-[10px] tracking-wider border border-brand-accent/20">
                UPLOADED HOUSEHOLD DATA
              </div>
            </div>
            
                        {/* KPI Row */}
            <section className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
              <Metric label="Total Consumption" value={(dashboard.total_consumption ?? dashboard.consumption?.kwh)?.toFixed(0)} suffix="kWh" />
              {isYearView ? (
                <Metric label="Peak Month Demand" value={dashboard.peak_consumption?.toFixed(0)} suffix="kWh" tone="amber" />
              ) : (
                <Metric label="Daily Average" value={((dashboard.total_consumption ?? dashboard.consumption?.kwh) / (dashboard.daily_data?.length || 1)).toFixed(1)} suffix="kWh/day" tone="blue" />
              )}
              
              <div className="bg-white border border-line rounded-2xl p-5 shadow-sm flex flex-col justify-between relative overflow-hidden">
                <div className="flex justify-between items-start mb-2">
                  <span className="text-[10px] font-bold text-muted uppercase tracking-widest block">Electricity Cost</span>
                  {dashboard.cost?.source && <CostBadge source={dashboard.cost.source} />}
                </div>
                {dashboard.cost?.amount_inr != null ? (
                  <>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xl font-bold text-ink">₹{dashboard.cost.amount_inr.toFixed(0)}</span>
                    </div>
                    {dashboard.effective_cost_per_kwh && (
                      <span className="text-xs text-muted block mt-1">
                        Effective bill cost: ₹{dashboard.effective_cost_per_kwh.toFixed(2)}/kWh
                      </span>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-muted mt-2">Cost data unavailable</div>
                )}
              </div>

              <div className="bg-white border border-line rounded-2xl p-5 shadow-sm flex flex-col justify-between">
                <span className="text-[10px] font-bold text-muted uppercase tracking-widest block mb-2">Previous Period</span>
                {dashboard.previous_period?.cost_inr != null ? (
                  <>
                    <div className="flex items-baseline gap-1">
                      <span className="text-xl font-bold text-ink">₹{dashboard.previous_period.cost_inr.toFixed(0)}</span>
                    </div>
                    {dashboard.comparison?.cost_difference_inr != null && (
                      <div className={`mt-1 text-xs font-bold flex items-center gap-1 ${dashboard.comparison.cost_difference_inr > 0 ? 'text-red-500' : 'text-green-600'}`}>
                        {dashboard.comparison.cost_difference_inr > 0 ? '+' : ''}₹{dashboard.comparison.cost_difference_inr.toFixed(0)}
                        {' '}
                        ({dashboard.comparison.cost_change_percent > 0 ? '+' : ''}{dashboard.comparison.cost_change_percent.toFixed(1)}%)
                      </div>
                    )}
                  </>
                ) : (
                  <div className="text-sm text-muted mt-2">No previous bill available for comparison.</div>
                )}
              </div>
            </section>
            
            {dashboard.comparison && dashboard.previous_period && (
              <div className="mb-8 bg-paper rounded-2xl p-5 border border-line text-sm text-ink flex items-start gap-4">
                <div className="w-8 h-8 rounded-full bg-brand-accent/10 text-brand-accent flex items-center justify-center shrink-0 mt-0.5">
                  <Zap size={16} />
                </div>
                <div>
                  <h4 className="font-bold mb-1 text-brand-dark">Cost Insight</h4>
                  <p>
                    Your electricity cost {dashboard.comparison.cost_difference_inr > 0 ? "increased" : "decreased"} by ₹{Math.abs(dashboard.comparison.cost_difference_inr).toFixed(0)} compared with the previous available period.
                    Consumption changed by {dashboard.comparison.consumption_change_percent > 0 ? '+' : ''}{dashboard.comparison.consumption_change_percent.toFixed(1)}%.
                  </p>
                  {((dashboard.comparison.cost_difference_inr > 0 && dashboard.comparison.consumption_change_percent <= 0) || 
                    (dashboard.comparison.cost_difference_inr < 0 && dashboard.comparison.consumption_change_percent >= 0)) && (
                    <p className="mt-2 text-muted">
                      Your bill {dashboard.comparison.cost_difference_inr > 0 ? "increased" : "decreased"} even though consumption did the opposite. 
                      This may be related to changes in effective cost per kWh, fixed charges, taxes, or other bill components.
                    </p>
                  )}
                  {((dashboard.comparison.cost_difference_inr > 0 && dashboard.comparison.consumption_change_percent > 0) || 
                    (dashboard.comparison.cost_difference_inr < 0 && dashboard.comparison.consumption_change_percent < 0)) && (
                    <p className="mt-2 text-muted">
                      This suggests that {dashboard.comparison.consumption_change_percent > 0 ? "higher" : "lower"} consumption was a major contributor to the {dashboard.comparison.cost_difference_inr > 0 ? "increase" : "decrease"} in your bill.
                    </p>
                  )}
                </div>
              </div>
            )}

                        {/* Main Visuals Row */}
            <section className="grid lg:grid-cols-2 gap-6 mb-8">
              {/* Main Chart - Consumption */}
              <article className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <p className="text-xs font-bold tracking-widest text-brand-accent mb-1">CONSUMPTION TREND</p>
                <h2 className="text-xl font-bold text-brand-dark mb-6">
                  {isYearView ? `Monthly Consumption` : `Daily Consumption`}
                </h2>
                
                {isYearView ? (
                  <SimpleBarChart 
                    data={dashboard.monthly_data} 
                    xKey="month" 
                    yKey="energy_kwh" 
                    color="#2878c8" 
                    onClick={(data) => {
                      if (data?.activePayload?.[0]?.payload) {
                        const payload = data.activePayload[0].payload;
                        const monthNum = payload.month_num;
                        const monthStr = monthNum < 10 ? `0${monthNum}` : `${monthNum}`;
                        router.push(`/dashboard?period=${activePeriod}-${monthStr}`);
                      }
                    }}
                  />
                ) : (
                  <SimpleBarChart data={dashboard.daily_data} xKey="date" yKey="energy_kwh" color="#2878c8" />
                )}
              </article>
              
              {/* Main Chart - Cost */}
              <article className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <div className="flex justify-between items-start mb-1">
                  <p className="text-xs font-bold tracking-widest text-brand-accent">ELECTRICITY COST</p>
                  {dashboard.cost?.source && <CostBadge source={dashboard.cost.source} />}
                </div>
                <h2 className="text-xl font-bold text-brand-dark mb-6">
                  {isYearView ? `Monthly Cost (₹)` : `Daily Cost (₹)`}
                </h2>
                
                {isYearView ? (
                  <SimpleBarChart 
                    data={dashboard.monthly_data} 
                    xKey="month" 
                    yKey="cost_inr" 
                    color="#10b981" 
                    onClick={(data) => {
                      if (data?.activePayload?.[0]?.payload) {
                        const payload = data.activePayload[0].payload;
                        const monthNum = payload.month_num;
                        const monthStr = monthNum < 10 ? `0${monthNum}` : `${monthNum}`;
                        router.push(`/dashboard?period=${activePeriod}-${monthStr}`);
                      }
                    }}
                  />
                ) : (
                  <SimpleBarChart data={dashboard.daily_data} xKey="date" yKey="cost_inr" color="#10b981" />
                )}
              </article>
            </section>

            {/* Navigation Cards */}
            <section className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              <NavCard href="/forecast" title="Forecast" desc="Explore future demand" icon={<TrendingUp className="text-blue w-6 h-6"/>} />
              <NavCard href="/analytics" title="Analytics" desc="Understand consumption patterns" icon={<BarChart2 className="text-brand-accent w-6 h-6"/>} />
              <NavCard href="/smart-grid" title="Smart Grid" desc="Identify peak periods and optimization opportunities" icon={<Activity className="text-amber w-6 h-6"/>} />
              <NavCard href="/recommendations" title="Recommendations" desc="See recommended actions" icon={<HelpCircle className="text-green w-6 h-6"/>} />
            </section>
          </>
        )}
      </State>
    </Shell>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={
      <Shell>
        <Header 
          eyebrow="ENERGY OVERVIEW" 
          title="Your household energy at a glance" 
          description="Loading dashboard data..." 
        />
        <div className="p-12 text-center text-muted">Loading...</div>
      </Shell>
    }>
      <DashboardContent />
    </Suspense>
  );
}

function NavCard({ href, title, desc, icon }: { href: string, title: string, desc: string, icon: React.ReactNode }) {
  return (
    <Link href={href} className="group bg-white border border-line hover:border-brand-accent rounded-2xl p-5 shadow-sm transition-all hover:shadow-md flex flex-col h-full">
      <div className="bg-paper w-12 h-12 rounded-xl flex items-center justify-center mb-4 group-hover:scale-110 transition-transform">
        {icon}
      </div>
      <h3 className="font-bold text-ink mb-1 flex items-center justify-between">
        {title}
        <ArrowRight size={16} className="text-muted group-hover:text-brand-accent group-hover:translate-x-1 transition-all" />
      </h3>
      <p className="text-sm text-muted">{desc}</p>
    </Link>
  );
}
