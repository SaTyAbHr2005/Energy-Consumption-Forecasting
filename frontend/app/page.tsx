import Link from "next/link";
import { ArrowRight, BarChart2, TrendingUp, Zap, Server, Activity, ShieldCheck, HardDrive, Calculator, CheckCircle2, AlertTriangle, Receipt } from "lucide-react";
import { createClient } from "@/utils/supabase/server";

export default async function Home() {
  const supabase = createClient();
  const { data: { session } } = await supabase.auth.getSession();
  const isLoggedIn = !!session;

  return (
    <div className="min-h-screen bg-paper font-sans text-ink selection:bg-brand-accent selection:text-white flex flex-col">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 p-6 z-50 bg-paper/80 backdrop-blur-md border-b border-line">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded bg-brand-dark flex items-center justify-center text-white font-bold text-sm shadow-sm">⚡</div>
            <b className="text-xl text-brand-dark tracking-tight">EnergySense</b>
          </div>
          <div className="flex gap-4">
            {isLoggedIn ? (
              <>
                <Link href="/dashboard" className="hidden sm:flex items-center px-4 py-2 font-medium text-muted hover:text-brand-dark transition-colors">
                  Dashboard
                </Link>
                <Link href="/upload" className="flex items-center gap-2 bg-brand-dark hover:bg-ink text-white px-5 py-2.5 rounded-full text-sm font-bold transition-all shadow-md">
                  Upload Data
                </Link>
              </>
            ) : (
              <>
                <Link href="/login" className="hidden sm:flex items-center px-4 py-2 font-medium text-muted hover:text-brand-dark transition-colors">
                  Sign In
                </Link>
                <Link href="/register" className="flex items-center gap-2 bg-brand-dark hover:bg-ink text-white px-5 py-2.5 rounded-full text-sm font-bold transition-all shadow-md">
                  Create Account
                </Link>
              </>
            )}
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <header className="pt-40 pb-20 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green/10 text-green font-bold text-xs tracking-wider mb-8 border border-green/20">
            ADVANCED FORECASTING & DECISION SUPPORT
          </div>
          <h1 className="text-5xl md:text-7xl font-extrabold text-brand-dark tracking-tight leading-tight mb-8">
            Understand. <span className="text-brand-accent">Forecast.</span> Optimize.
          </h1>
          <p className="text-xl text-muted leading-relaxed mb-12 max-w-2xl mx-auto">
            Household energy consumption forecasting and forecast-based smart-grid decision support. 
            Upload your historical data to generate personalized insights.
          </p>
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
            {isLoggedIn ? (
              <>
                <Link href="/upload" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-brand-accent hover:bg-green text-white px-8 py-4 rounded-full text-lg font-bold transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5">
                  Upload Your Energy Data
                  <ArrowRight size={20} />
                </Link>
                <Link href="/dashboard" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-white hover:bg-paper text-ink border border-line px-8 py-4 rounded-full text-lg font-bold transition-all shadow-sm">
                  Explore Dashboard
                </Link>
              </>
            ) : (
              <>
                <Link href="/register" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-brand-accent hover:bg-green text-white px-8 py-4 rounded-full text-lg font-bold transition-all shadow-lg hover:shadow-xl hover:-translate-y-0.5">
                  Sign Up For Free
                  <ArrowRight size={20} />
                </Link>
                <Link href="/login" className="w-full sm:w-auto flex items-center justify-center gap-2 bg-white hover:bg-paper text-ink border border-line px-8 py-4 rounded-full text-lg font-bold transition-all shadow-sm">
                  Log In
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Visual Workflow */}
      <section className="py-20 px-6 bg-white border-y border-line">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-brand-dark mb-4">How it works</h2>
            <p className="text-muted">A seamless pipeline from raw data to actionable insights.</p>
          </div>
          
          <div className="flex flex-col md:flex-row items-center justify-between gap-4 md:gap-0 relative">
            <div className="hidden md:block absolute top-1/2 left-0 right-0 h-1 bg-line -translate-y-1/2 z-0"></div>
            
            <WorkflowStep icon={<HardDrive size={24} />} title="CSV Upload" desc="Provide historical usage" />
            <WorkflowStep icon={<ShieldCheck size={24} />} title="Data Validation" desc="Schema & quality check" />
            <WorkflowStep icon={<Activity size={24} />} title="Time-Series" desc="Processing & aggregation" />
            <WorkflowStep icon={<TrendingUp size={24} />} title="Forecasting" desc="XGBoost prediction" />
            <WorkflowStep icon={<Zap size={24} />} title="Smart-Grid" desc="Peak detection & TOU" />
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="py-24 px-6">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-brand-dark mb-4">System Capabilities</h2>
            <p className="text-muted">Advanced analytics powered by specialized machine learning models.</p>
          </div>
          
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <CapabilityCard 
              icon={<BarChart2 className="text-blue" size={32} />}
              title="Energy Analytics"
              desc="Deep dive into your consumption patterns by hour, day, and week to understand your baseline usage."
            />
            <CapabilityCard 
              icon={<TrendingUp className="text-brand-accent" size={32} />}
              title="Forecasting"
              desc="Accurate 1-hour and 24-hour predictions using a highly optimized XGBoost production model."
            />
            <CapabilityCard 
              icon={<AlertTriangle className="text-amber" size={32} />}
              title="Peak Demand Detection"
              desc="Automatically identifies statistical peaks tailored to your specific household baseline."
            />
            <CapabilityCard 
              icon={<Calculator className="text-ink" size={32} />}
              title="TOU Simulation"
              desc="Illustrative Time-of-Use pricing simulation to show the financial impact of shifting loads."
            />
            <CapabilityCard 
              icon={<Zap className="text-green" size={32} />}
              title="Smart Recommendations"
              desc="Actionable, prioritized recommendations based on your unique consumption forecast and detected peaks."
            />
            <CapabilityCard 
              icon={<Receipt className="text-blue" size={32} />}
              title="Bill Ingestion & OCR"
              desc="Upload images of your electricity bills to automatically extract and track your actual energy costs."
            />
          </div>
        </div>
      </section>

      {/* What this system does / Disclaimer */}
      <section className="py-20 px-6 bg-brand-dark text-white mt-auto">
        <div className="max-w-4xl mx-auto">
          <div className="bg-white/5 border border-white/10 rounded-3xl p-8 md:p-12 text-center">
            <Server className="w-12 h-12 text-white/50 mx-auto mb-6" />
            <h2 className="text-2xl font-bold mb-4">What this system does</h2>
            <p className="text-white/70 leading-relaxed mb-8 max-w-2xl mx-auto">
              EnergySense is a forecasting and decision-support simulation tool. It uses historical CSV data and advanced machine learning to predict future usage patterns and generate recommendations.
            </p>
            <div className="grid sm:grid-cols-2 gap-4 text-left">
              <div className="space-y-3">
                <DisclaimerItem text="No live smart meter connection" />
                <DisclaimerItem text="No automatic appliance control" />
              </div>
              <div className="space-y-3">
                <DisclaimerItem text="No real-time grid integration" />
                <DisclaimerItem text="Savings are illustrative estimates" />
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}

function WorkflowStep({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="relative z-10 flex flex-col items-center text-center w-48 bg-paper py-4 md:py-0">
      <div className="w-16 h-16 rounded-full bg-white border-4 border-line flex items-center justify-center text-brand-dark shadow-sm mb-4">
        {icon}
      </div>
      <h3 className="font-bold text-ink mb-1">{title}</h3>
      <p className="text-xs text-muted leading-tight">{desc}</p>
    </div>
  );
}

function CapabilityCard({ icon, title, desc }: { icon: React.ReactNode, title: string, desc: string }) {
  return (
    <div className="bg-white p-8 rounded-3xl border border-line shadow-sm hover:shadow-md hover:border-brand-accent transition-all">
      <div className="w-16 h-16 rounded-2xl bg-paper flex items-center justify-center mb-6">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-ink mb-3">{title}</h3>
      <p className="text-muted leading-relaxed">{desc}</p>
    </div>
  );
}

function DisclaimerItem({ text }: { text: string }) {
  return (
    <div className="flex items-center gap-3 text-white/60 text-sm bg-white/5 p-3 rounded-xl">
      <XCircle size={16} className="text-white/30 shrink-0" />
      {text}
    </div>
  );
}

import { XCircle } from "lucide-react";
