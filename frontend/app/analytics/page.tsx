"use client";
import { Header, Shell, State, useActiveUpload, useUserAnalysis, useUserCostAnalytics, CostBadge } from "../components";
import { ConsumptionAreaChart, SimpleBarChart } from "../components/charts";
import { BarChart2, Calendar, Clock, Activity } from "lucide-react";
import { useMemo } from "react";

export default function AnalyticsPage() {
  const { uploadId } = useActiveUpload();
  const { data: userAnalysis, loading, error } = useUserAnalysis();
  const { data: costData, loading: costLoading } = useUserCostAnalytics();

  const hourlyData = userAnalysis?.historical_series ?? [];
  const hasData = hourlyData.length > 0;

  // Calculate Time-of-day profile from hourly data
  const timeOfDayProfile = useMemo(() => {
    if (!hourlyData.length) return [];
    const sums = new Array(24).fill(0);
    const counts = new Array(24).fill(0);
    
    hourlyData.forEach((row: any) => {
      if (!row.timestamp) return;
      try {
        const hourStr = row.timestamp.split(" ")[1];
        if (hourStr) {
          const hour = parseInt(hourStr.split(":")[0]);
          if (!isNaN(hour) && row.energy_kwh != null) {
            sums[hour] += Number(row.energy_kwh);
            counts[hour] += 1;
          }
        }
      } catch (e) {}
    });
    
    return sums.map((s, i) => ({
      hour: `${i.toString().padStart(2, '0')}:00`,
      energy_kwh: counts[i] > 0 ? (s / counts[i]) : 0
    }));
  }, [hourlyData]);

  const weekdayData = useMemo(() => {
    if (!hourlyData.length) return [];
    const days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
    const sums = new Array(7).fill(0);
    const counts = new Array(7).fill(0);
    hourlyData.forEach((row: any) => {
      if (!row.timestamp) return;
      try {
        // Timestamp format: "2010-09-02 21:00:00"
        const dateParts = row.timestamp.split(" ")[0].split("-");
        const dateObj = new Date(parseInt(dateParts[0]), parseInt(dateParts[1])-1, parseInt(dateParts[2]));
        const day = dateObj.getDay();
        if (!isNaN(day) && row.energy_kwh != null) {
          sums[day] += Number(row.energy_kwh);
          counts[day] += 1;
        }
      } catch(e) {}
    });
    return sums.map((s, i) => ({
      day_of_week: days[i],
      average_kwh: counts[i] > 0 ? (s / counts[i]) : 0
    }));
  }, [hourlyData]);

  const dailyData = useMemo(() => {
    if (!hourlyData.length) return [];
    const dailyMap = new Map();
    hourlyData.forEach((row: any) => {
      if (!row.timestamp || row.energy_kwh == null) return;
      try {
        const dateStr = row.timestamp.split(" ")[0];
        const val = Number(row.energy_kwh);
        dailyMap.set(dateStr, (dailyMap.get(dateStr) || 0) + val);
      } catch(e) {}
    });
    return Array.from(dailyMap.entries()).map(([date, total_kwh]) => ({ date, total_kwh }));
  }, [hourlyData]);

  // Extract simple insights
  const insights = useMemo(() => {
    if (!timeOfDayProfile.length || !weekdayData.length) return null;
    
    const maxHour = [...timeOfDayProfile].sort((a, b) => b.energy_kwh - a.energy_kwh)[0];
    const minHour = [...timeOfDayProfile].sort((a, b) => a.energy_kwh - b.energy_kwh)[0];
    
    const maxDay = [...weekdayData].sort((a, b) => b.average_kwh - a.average_kwh)[0];
    
    return {
      highestHour: maxHour.hour,
      lowestHour: minHour.hour,
      highestDay: maxDay.day_of_week
    };
  }, [timeOfDayProfile, weekdayData]);

  if (!uploadId) {
    return (
      <Shell>
        <Header eyebrow="ANALYTICS" title="Consumption Patterns" description="Deep dive into your historical energy baseline." />
        <div className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm max-w-2xl mx-auto mt-8">
          <BarChart2 className="w-12 h-12 text-muted mx-auto mb-4" />
          <h2 className="text-xl font-bold text-brand-dark mb-2">No household data available.</h2>
          <p className="text-muted">Upload a CSV dataset to explore these visual analytics.</p>
        </div>
      </Shell>
    );
  }

  return (
    <Shell>
      <Header 
        eyebrow="ANALYTICS" 
        title="Consumption Patterns" 
        description="Deep dive into your historical energy baseline." 
      />
      
      <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-brand-accent/10 text-brand-accent font-bold text-[10px] tracking-wider mb-8 border border-brand-accent/20">
        UPLOADED HOUSEHOLD DATA • HISTORICAL
      </div>

      <State loading={loading} error={error}>
        {hasData && (
          <div className="flex flex-col gap-8">
            {/* Cost Analysis Row */}
            {costData?.has_data && (
              <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <div className="flex justify-between items-start mb-6">
                  <h3 className="font-bold text-ink flex items-center gap-2">
                    ELECTRICITY COST ANALYSIS
                  </h3>
                  <CostBadge source="estimated" />
                </div>
                
                <div className="grid md:grid-cols-4 gap-4 mb-8">
                  <div className="p-4 bg-paper rounded-xl border border-line">
                    <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Total Cost Analyzed</span>
                    <strong className="text-2xl text-ink">₹{costData.total_cost?.toFixed(0)}</strong>
                    <span className="text-xs text-muted block mt-1">Over {costData.months_analyzed} month(s)</span>
                  </div>
                  <div className="p-4 bg-paper rounded-xl border border-line">
                    <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Average Monthly</span>
                    <strong className="text-2xl text-ink">₹{costData.average_monthly_cost?.toFixed(0)}</strong>
                  </div>
                  <div className="p-4 bg-paper rounded-xl border border-line">
                    <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Highest Month</span>
                    <strong className="text-2xl text-red-500">₹{costData.highest_cost_month?.cost?.toFixed(0)}</strong>
                    <span className="text-xs text-muted block mt-1">{costData.highest_cost_month?.period}</span>
                  </div>
                  <div className="p-4 bg-paper rounded-xl border border-line">
                    <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Lowest Month</span>
                    <strong className="text-2xl text-green-600">₹{costData.lowest_cost_month?.cost?.toFixed(0)}</strong>
                    <span className="text-xs text-muted block mt-1">{costData.lowest_cost_month?.period}</span>
                  </div>
                </div>

                <div className="grid lg:grid-cols-2 gap-6">
                  <div>
                    <h4 className="font-bold mb-4 text-sm uppercase tracking-wider text-muted">Consumption → Cost</h4>
                    <div className="overflow-x-auto">
                      <table className="w-full text-sm text-left">
                        <thead className="bg-paper text-muted uppercase text-[10px] font-bold tracking-wider">
                          <tr>
                            <th className="px-4 py-2 rounded-tl-lg rounded-bl-lg">Metric</th>
                            <th className="px-4 py-2 text-right">Consumption</th>
                            <th className="px-4 py-2 text-right">Est. Bill Cost</th>
                            <th className="px-4 py-2 text-right rounded-tr-lg rounded-br-lg">Rate</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-b border-line">
                            <td className="px-4 py-3 font-medium">All-Time Average</td>
                            <td className="px-4 py-3 text-right">{(costData.total_consumption / costData.months_analyzed).toFixed(1)} kWh</td>
                            <td className="px-4 py-3 text-right">₹{(costData.total_cost / costData.months_analyzed).toFixed(0)}</td>
                            <td className="px-4 py-3 text-right">₹{costData.rate?.toFixed(2)}/kWh</td>
                          </tr>
                          <tr className="border-b border-line">
                            <td className="px-4 py-3 font-medium">Highest Month</td>
                            <td className="px-4 py-3 text-right">{(costData.highest_cost_month?.cost / costData.rate).toFixed(1)} kWh</td>
                            <td className="px-4 py-3 text-right">₹{costData.highest_cost_month?.cost?.toFixed(0)}</td>
                            <td className="px-4 py-3 text-right">₹{costData.rate?.toFixed(2)}/kWh</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                  <div className="bg-paper rounded-xl border border-line p-6 flex flex-col items-center justify-center text-center">
                    <span className="text-xs font-bold tracking-widest text-muted mb-2 uppercase">Bill Component Analysis</span>
                    <p className="text-sm text-muted">Placeholder for future OCR bill breakdown (Fixed vs Variable vs Taxes).</p>
                  </div>
                </div>
              </div>
            )}

            
            {/* Top row: Insights + Weekday */}
            <div className="grid lg:grid-cols-3 gap-6">
              <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
                <h3 className="font-bold text-ink mb-6 flex items-center gap-2"><Activity size={18} className="text-brand-accent"/> Consumption Insights</h3>
                
                {insights && (
                  <div className="space-y-4">
                    <div className="p-4 bg-paper rounded-xl border border-line">
                      <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Highest Avg Demand</span>
                      <strong className="text-xl text-ink">{insights.highestHour}</strong>
                    </div>
                    <div className="p-4 bg-paper rounded-xl border border-line">
                      <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Lowest Avg Demand</span>
                      <strong className="text-xl text-ink">{insights.lowestHour}</strong>
                    </div>
                    <div className="p-4 bg-paper rounded-xl border border-line">
                      <span className="block text-xs font-bold uppercase tracking-wider text-muted mb-1">Peak Day of Week</span>
                      <strong className="text-xl text-ink">{insights.highestDay}</strong>
                    </div>
                  </div>
                )}
              </div>
              
              <div className="lg:col-span-2 bg-white border border-line rounded-3xl p-6 shadow-sm">
                <h3 className="font-bold text-ink mb-6 flex items-center gap-2"><Calendar size={18} className="text-blue"/> Average consumption by day</h3>
                <SimpleBarChart data={weekdayData} xKey="day_of_week" yKey="average_kwh" color="#2878c8" />
              </div>
            </div>

            {/* Middle row: Time of Day */}
            <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
              <h3 className="font-bold text-ink mb-6 flex items-center gap-2"><Clock size={18} className="text-amber"/> 24-Hour Average Profile</h3>
              <ConsumptionAreaChart data={timeOfDayProfile} timeKey="hour" color="#e39a29" />
              <p className="text-sm text-center text-muted mt-4">Aggregated baseline profile across all uploaded days.</p>
            </div>

            {/* Bottom row: Daily timeline */}
            <div className="bg-white border border-line rounded-3xl p-6 shadow-sm">
              <h3 className="font-bold text-ink mb-6 flex items-center gap-2"><BarChart2 size={18} className="text-green"/> Daily energy consumption</h3>
              <SimpleBarChart data={dailyData} xKey="date" yKey="total_kwh" color="#138a68" />
            </div>

          </div>
        )}
      </State>
    </Shell>
  );
}
