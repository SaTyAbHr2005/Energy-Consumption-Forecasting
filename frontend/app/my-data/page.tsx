"use client";

import { createClient } from "@/utils/supabase/client";
import { useFetch, Header, State, useActiveUpload, Shell, API } from "@/app/components";
import { Database, Calendar, FileText, CheckCircle, Zap, Receipt, TrendingUp, TrendingDown, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";

export default function MyDataPage() {
  const { data: datasets, loading, error } = useFetch<any[]>("/api/datasets", []);
  const { data: bills, loading: billsLoading } = useFetch<any[]>("/api/bills", []);
  const { uploadId, saveUpload } = useActiveUpload();
  const router = useRouter();

  const { chartData, comparison } = useMemo(() => {
    if (!bills || bills.length === 0) return { chartData: [], comparison: null };
    
    const chartData = [...bills].reverse().map(b => ({
      name: b.bill_date.replace(" 2026", ""), // shorten for chart
      cost: b.cost,
      consumption: b.consumption
    }));
    
    let comparison = null;
    if (bills.length > 1) {
      const latest = bills[0];
      const previous = bills[1];
      const diff = latest.cost - previous.cost;
      const percent = previous.cost > 0 ? (diff / previous.cost * 100).toFixed(1) : "0";
      comparison = {
        diff,
        percent,
        latestDate: latest.bill_date,
        isHigher: diff > 0
      };
    }
    
    return { chartData, comparison };
  }, [bills]);

  useEffect(() => {
    if (datasets && uploadId) {
      if (!datasets.some(d => d.id === uploadId)) {
        saveUpload("");
      }
    }
  }, [datasets, uploadId, saveUpload]);

  const handleSelect = (id: string, end_timestamp?: string) => {
    saveUpload(id);
    if (end_timestamp) {
      const period = end_timestamp.substring(0, 7); // '2026-08'
      router.push(`/dashboard?period=${period}`);
    } else {
      router.push("/dashboard");
    }
  };

  const handleDeleteDataset = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this dataset completely?")) return;
    
    const { data: { session } } = await createClient().auth.getSession();
    await fetch(`${API}/api/datasets/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${session?.access_token}` }
    });
    
    if (uploadId === id) {
      saveUpload("");
    }
    window.location.reload();
  };

  const handleDeleteBill = async (id: number, e: React.MouseEvent) => {
    e.stopPropagation();
    if (!confirm("Are you sure you want to delete this bill completely?")) return;
    
    const { data: { session } } = await createClient().auth.getSession();
    await fetch(`${API}/api/bills/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${session?.access_token}` }
    });
    
    window.location.reload();
  };

  return (
    <Shell>
      <Header 
        eyebrow="My Data" 
        title="Uploaded Datasets & Bills" 
        description="Select an existing dataset to perform analysis, or view your tracked electricity bills." 
        action={
          <button onClick={() => router.push("/upload")} className="bg-brand-dark text-white px-5 py-2.5 rounded-xl text-sm font-bold shadow-sm hover:bg-ink transition-colors flex items-center gap-2">
            <Database size={16} />
            New Upload
          </button>
        }
      />

      <div className="mb-8">
        <h2 className="text-xl font-bold text-brand-dark mb-4 flex items-center gap-2"><Database size={20} /> Smart Meter Datasets</h2>
        <State loading={loading} error={error}>
          {datasets?.length === 0 ? (
            <div className="bg-white border border-line rounded-3xl p-12 text-center shadow-sm max-w-2xl mx-auto">
              <div className="w-16 h-16 bg-brand-accent/10 text-brand-accent rounded-full flex items-center justify-center mx-auto mb-6">
                <Database size={32} />
              </div>
              <h2 className="text-xl font-bold text-brand-dark mb-2">No datasets found</h2>
              <p className="text-muted mb-8">
                You haven't uploaded any smart meter data yet. Upload your first CSV file to unlock forecasts and insights.
              </p>
              <button onClick={() => router.push("/upload")} className="bg-brand-dark text-white px-6 py-3 rounded-xl font-bold shadow-sm hover:bg-ink transition-colors inline-block">
                Upload Dataset
              </button>
            </div>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {datasets?.map(dataset => (
                <div 
                  key={dataset.id} 
                  className={`bg-white border rounded-2xl p-6 transition-all cursor-pointer group ${
                    uploadId === dataset.id 
                      ? "border-brand-accent shadow-md ring-1 ring-brand-accent" 
                      : "border-line shadow-sm hover:border-brand-accent/50 hover:shadow-md"
                  }`}
                  onClick={() => handleSelect(dataset.id, dataset.end_timestamp)}
                >
                  <div className="flex justify-between items-start mb-4">
                    <div className="flex items-center gap-3">
                      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${uploadId === dataset.id ? 'bg-brand-accent text-white' : 'bg-paper text-muted group-hover:bg-brand-accent/10 group-hover:text-brand-accent'} transition-colors`}>
                        <FileText size={20} />
                      </div>
                      <div>
                        <h3 className="font-bold text-ink truncate max-w-[150px]" title={dataset.file_name}>{dataset.file_name}</h3>
                        <p className="text-xs text-muted flex items-center gap-1">
                          <Calendar size={12} />
                          {new Date(dataset.created_at).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {uploadId === dataset.id && (
                        <span className="flex items-center gap-1 text-[10px] font-bold uppercase tracking-wider text-brand-accent bg-brand-accent/10 px-2 py-1 rounded-lg">
                          <CheckCircle size={12} /> Active
                        </span>
                      )}
                      <button 
                        onClick={(e) => handleDeleteDataset(dataset.id, e)}
                        className="text-muted hover:text-red p-1 rounded transition-colors"
                        title="Delete Dataset"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-6">
                    <div className="bg-paper p-3 rounded-xl border border-line/50">
                      <span className="block text-[10px] font-bold text-muted uppercase tracking-wider mb-1">Records</span>
                      <strong className="text-sm text-ink">{dataset.record_count.toLocaleString()}</strong>
                    </div>
                    <div className="bg-paper p-3 rounded-xl border border-line/50">
                      <span className="block text-[10px] font-bold text-muted uppercase tracking-wider mb-1">Interval</span>
                      <strong className="text-sm text-ink">{dataset.interval_minutes}m</strong>
                    </div>
                  </div>

                  <button className={`w-full py-2.5 rounded-xl text-sm font-bold flex items-center justify-center gap-2 transition-colors ${
                    uploadId === dataset.id 
                      ? "bg-brand-accent/10 text-brand-accent" 
                      : "bg-paper text-ink group-hover:bg-brand-dark group-hover:text-white"
                  }`}>
                    {uploadId === dataset.id ? "Currently Active" : "Analyze Dataset"}
                    {uploadId !== dataset.id && <Zap size={14} className={uploadId === dataset.id ? "" : "opacity-50 group-hover:opacity-100"} />}
                  </button>
                </div>
              ))}
            </div>
          )}
        </State>
      </div>

      <div className="mb-8">
        <h2 className="text-xl font-bold text-brand-dark mb-4 flex items-center gap-2 mt-8"><Receipt size={20} /> Tracked Electricity Bills</h2>
        <State loading={billsLoading}>
          {bills?.length === 0 ? (
            <div className="bg-white border border-line rounded-3xl p-8 text-center shadow-sm">
              <p className="text-muted">You haven't uploaded any electricity bills yet. Go to the upload page to scan your first bill!</p>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Header Stats & Comparison */}
              <div className="flex flex-col md:flex-row gap-4 items-stretch">
                <div className="bg-white border border-line rounded-2xl p-6 shadow-sm flex-1 flex flex-col justify-center">
                  <span className="text-sm text-muted font-bold uppercase tracking-wider mb-2">Bills Tracked</span>
                  <strong className="text-3xl text-brand-dark">{bills?.length || 0}</strong>
                  <span className="text-sm text-muted mt-2">Saved to your yearly history</span>
                </div>
                
                {comparison && (
                  <div className="bg-white border border-line rounded-2xl p-6 shadow-sm flex-[2] flex items-center gap-4">
                    <div className={`w-14 h-14 rounded-full flex items-center justify-center ${comparison.isHigher ? 'bg-red/10 text-red' : 'bg-green/10 text-green-700'}`}>
                      {comparison.isHigher ? <TrendingUp size={28} /> : <TrendingDown size={28} />}
                    </div>
                    <div>
                      <h3 className="font-bold text-lg text-ink mb-1">Month-over-Month Comparison</h3>
                      <p className="text-muted text-sm">
                        Your latest bill ({comparison.latestDate}) is <strong className={comparison.isHigher ? 'text-red' : 'text-green-700'}>₹{Math.abs(comparison.diff).toLocaleString(undefined, { minimumFractionDigits: 2 })} ({comparison.percent}%) {comparison.isHigher ? 'higher' : 'lower'}</strong> than the previous bill.
                      </p>
                    </div>
                  </div>
                )}
              </div>

              {/* Chart */}
              {chartData.length > 0 && (
                <div className="bg-white border border-line rounded-2xl p-6 shadow-sm h-80">
                  <h3 className="font-bold text-ink mb-6">Yearly Cost Trend</h3>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#E5E7EB" />
                      <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fill: '#6B7280', fontSize: 12 }} dy={10} />
                      <YAxis axisLine={false} tickLine={false} tick={{ fill: '#6B7280', fontSize: 12 }} tickFormatter={(val) => `₹${val}`} />
                      <Tooltip 
                        cursor={{ fill: '#F3F4F6' }}
                        contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                        formatter={(value: any) => [`₹${Number(value).toLocaleString()}`, 'Cost']}
                      />
                      <Bar dataKey="cost" fill="#0C4A34" radius={[4, 4, 0, 0]} maxBarSize={60} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {/* Grid of Bills */}
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 mt-6">
                {bills?.map((bill: any) => (
                  <div key={bill.id} className="bg-white border border-line rounded-2xl p-6 shadow-sm">
                    <div className="flex justify-between items-start mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-purple/10 text-purple flex items-center justify-center">
                          <Receipt size={20} />
                        </div>
                        <div>
                          <h3 className="font-bold text-ink">{bill.bill_date}</h3>
                          <p className="text-[10px] text-muted flex items-center gap-1">
                            <Calendar size={10} /> Added {new Date(bill.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <button 
                        onClick={(e) => handleDeleteBill(bill.id, e)}
                        className="text-muted hover:text-red p-1 rounded transition-colors"
                        title="Delete Bill"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                    
                    <div className="space-y-3">
                      <div className="flex justify-between items-end border-b border-line pb-2">
                        <span className="text-sm text-muted">Cost</span>
                        <strong className="text-lg text-ink">₹{bill.cost.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                      </div>
                      <div className="flex justify-between items-end">
                        <span className="text-sm text-muted">Consumption</span>
                        <strong className="text-lg text-brand-accent">{bill.consumption} kWh</strong>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </State>
      </div>
    </Shell>
  );
}
