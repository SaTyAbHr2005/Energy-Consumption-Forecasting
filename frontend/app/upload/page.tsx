"use client";

import { useState } from "react";
import { Header, Shell, useActiveUpload, API } from "../components";
import { UploadCloud, CheckCircle2, AlertCircle, XCircle, ArrowRight, FileText, Loader2, Image as ImageIcon } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { createClient } from "@/utils/supabase/client";

type ValidationResult = {
  valid: boolean;
  records?: number;
  errors?: string[];
  warnings?: string[];
  forecasting_readiness?: string;
  upload_id?: string;
  time_coverage?: string; 
  extracted_cost?: number;
  extracted_consumption?: number;
  extracted_date?: string;
};

export default function UploadPage() {
  const router = useRouter();
  const { saveUpload } = useActiveUpload();
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValidationResult | null>(null);
  const [stage, setStage] = useState(0);
  const [uploadType, setUploadType] = useState<"meter" | "bill">("meter");

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files || e.target.files.length === 0) return;
    const selectedFile = e.target.files[0];
    setFile(selectedFile);
    setResult(null);
    setStage(0);
  }

  async function analyzeDataset() {
    if (!file) return;
    setLoading(true);
    setStage(1);
    
    try {
      const supabase = createClient();
      const { data: { session } } = await supabase.auth.getSession();
      const headers: Record<string, string> = {};
      if (session?.access_token) {
        headers["Authorization"] = `Bearer ${session.access_token}`;
      }

      const form = new FormData();
      form.append("file", file);
      
      const endpoint = uploadType === "bill" ? "/api/upload/bill" : "/api/upload";
      const response = await fetch(`${API}${endpoint}`, { 
        method: "POST", 
        body: form,
        headers
      });
      const data = await response.json();
      
      if (uploadType === "meter") {
        setStage(2); // Time series prepared
        await new Promise(r => setTimeout(r, 600)); // Visual pacing
        setStage(3); // Forecast generated
        await new Promise(r => setTimeout(r, 600));
        setStage(4); // Smart grid
        await new Promise(r => setTimeout(r, 600));
        setStage(5); // Complete
      } else {
        setStage(2); // OCR Extraction
        await new Promise(r => setTimeout(r, 1000));
        setStage(5); // Complete
      }

      if (!response.ok) {
        setResult({ valid: false, errors: [data.detail ?? "Upload failed."] });
        return;
      }
      
      if (data.valid === false) {
        setResult({ valid: false, errors: data.errors || ["Validation failed."] });
        return;
      }
      
      setResult({ ...data, valid: true });
      if (data.upload_id) {
        saveUpload(data.upload_id);
      }
    } catch (err: any) {
      setResult({ valid: false, errors: [err.message] });
      setStage(0);
    } finally {
      setLoading(false);
    }
  }

  return (
    <Shell>
      <Header 
        eyebrow="DATA INGESTION" 
        title="Upload household energy data" 
        description="Provide a CSV file of your historical energy consumption or an image of your electricity bill." 
      />

      <div className="grid md:grid-cols-2 gap-8 max-w-5xl mx-auto">
        {/* Upload Zone */}
        <div className="flex flex-col gap-6">
          <div className="flex rounded-lg overflow-hidden border border-line p-1 bg-white">
            <button 
              onClick={() => { setUploadType("meter"); setFile(null); setResult(null); }}
              className={`flex-1 py-2 text-sm font-bold rounded-md transition-colors ${uploadType === "meter" ? 'bg-brand-dark text-white' : 'text-muted hover:bg-paper'}`}
            >
              Smart Meter (CSV)
            </button>
            <button 
              onClick={() => { setUploadType("bill"); setFile(null); setResult(null); }}
              className={`flex-1 py-2 text-sm font-bold rounded-md transition-colors ${uploadType === "bill" ? 'bg-brand-dark text-white' : 'text-muted hover:bg-paper'}`}
            >
              Electricity Bill (Image)
            </button>
          </div>

          <label className={`relative flex flex-col items-center justify-center p-12 border-2 border-dashed rounded-3xl cursor-pointer transition-all hover:bg-paper ${file ? 'border-brand-accent bg-paper' : 'border-line bg-white'}`}>
            <input 
              type="file" 
              className="hidden" 
              accept={uploadType === "meter" ? ".csv" : "image/*,.pdf"} 
              onChange={handleUpload} 
              disabled={loading} 
            />
            <div className="w-16 h-16 rounded-full bg-paper flex items-center justify-center mb-4">
              {uploadType === "meter" ? (
                <UploadCloud size={32} className={file ? "text-brand-accent" : "text-muted"} />
              ) : (
                <ImageIcon size={32} className={file ? "text-brand-accent" : "text-muted"} />
              )}
            </div>
            <h3 className="text-lg font-bold text-ink mb-2">{file ? file.name : (uploadType === "meter" ? "Select CSV File" : "Select Bill Image")}</h3>
            <p className="text-muted text-sm text-center">
              {file ? `${(file.size / 1024).toFixed(1)} KB` : "Drag and drop or click to browse"}
            </p>
          </label>

          {uploadType === "meter" && (
            <div className="bg-white p-6 rounded-3xl border border-line">
              <h4 className="font-bold text-sm mb-4">Required CSV Format</h4>
              <div className="bg-paper p-4 rounded-xl border border-line font-mono text-sm text-muted">
                timestamp,energy_consumption<br/>
                2026-08-01 00:00:00,0.043<br/>
                2026-08-01 00:15:00,0.035<br/>
                ...
              </div>
            </div>
          )}
          {uploadType === "bill" && (
            <div className="bg-white p-6 rounded-3xl border border-line">
              <h4 className="font-bold text-sm mb-4">Supported Formats</h4>
              <p className="text-sm text-muted">
                You can upload JPG, PNG, or PDF copies of your electricity bill. The system will extract your cost and consumption data automatically.
              </p>
            </div>
          )}
        </div>

        {/* Processing & Results */}
        <div>
          {file && !loading && !result && (
            <div className="bg-white border border-brand-accent/30 rounded-3xl p-8 shadow-sm flex flex-col items-center justify-center text-center h-full">
              {uploadType === "meter" ? <FileText className="w-12 h-12 text-brand-accent mb-4" /> : <ImageIcon className="w-12 h-12 text-brand-accent mb-4" />}
              <h3 className="text-xl font-bold mb-2">File Ready</h3>
              <p className="text-muted mb-8">{file.name}</p>
              <button 
                onClick={analyzeDataset}
                className="w-full py-4 rounded-xl bg-brand-dark hover:bg-ink text-white font-bold transition-colors"
              >
                {uploadType === "meter" ? "Analyze Dataset" : "Extract Bill Details"}
              </button>
            </div>
          )}

          {loading && (
            <div className="bg-white border border-line rounded-3xl p-8 shadow-sm h-full flex flex-col">
              <h3 className="font-bold mb-6 flex items-center gap-2"><Loader2 className="animate-spin text-brand-accent"/> Processing Pipeline</h3>
              {uploadType === "meter" ? (
                <div className="space-y-4 font-medium text-sm flex-1">
                  <PipelineStep label="Dataset validated" active={stage >= 1} done={stage > 1} />
                  <PipelineStep label="Time series prepared" active={stage >= 2} done={stage > 2} />
                  <PipelineStep label="Features generated" active={stage >= 3} done={stage > 3} />
                  <PipelineStep label="Forecast generated" active={stage >= 4} done={stage > 4} />
                  <PipelineStep label="Smart-grid analysis & Recommendations" active={stage >= 5} done={stage >= 5} />
                </div>
              ) : (
                <div className="space-y-4 font-medium text-sm flex-1">
                  <PipelineStep label="Uploading document..." active={stage >= 1} done={stage > 1} />
                  <PipelineStep label="Running AI OCR Extraction..." active={stage >= 2} done={stage > 2} />
                  <PipelineStep label="Validating billing data..." active={stage >= 5} done={stage >= 5} />
                </div>
              )}
            </div>
          )}

          {result && (
            <div className={`bg-white border rounded-3xl p-8 shadow-sm h-full flex flex-col ${result.valid ? 'border-green/30' : 'border-red/30'}`}>
              <div className="flex items-center gap-3 mb-6">
                {result.valid ? <CheckCircle2 className="w-8 h-8 text-green" /> : <XCircle className="w-8 h-8 text-red" />}
                <h3 className="text-xl font-bold text-ink">{result.valid ? (uploadType === "meter" ? "Dataset analyzed successfully" : "Bill Analyzed Successfully") : "Validation Failed"}</h3>
              </div>

              {result.valid && uploadType === "meter" && (
                <div className="flex-1 flex flex-col">
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div className="p-4 bg-paper rounded-xl">
                      <span className="block text-xs text-muted font-bold uppercase mb-1">Records</span>
                      <strong className="text-xl text-ink">{result.records?.toLocaleString() ?? "—"}</strong>
                    </div>
                    <div className="p-4 bg-paper rounded-xl">
                      <span className="block text-xs text-muted font-bold uppercase mb-1">Readiness</span>
                      <strong className="text-xl text-brand-accent capitalize">{result.forecasting_readiness?.replace("_", " ")}</strong>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-3 mb-8">
                    <StatusBadge valid={true} label="Schema" />
                    <StatusBadge valid={true} label="Timestamps" />
                    <StatusBadge valid={!(result.warnings && result.warnings.some(w => w.includes('missing')))} label="Missing Values" />
                    <StatusBadge valid={true} label="Chronology" />
                  </div>

                  <button 
                    onClick={() => router.push("/dashboard")}
                    className="mt-auto w-full py-4 rounded-xl bg-green hover:bg-brand-accent text-white font-bold transition-colors flex items-center justify-center gap-2"
                  >
                    View Dashboard <ArrowRight size={18} />
                  </button>
                </div>
              )}

              {result.valid && uploadType === "bill" && (
                <div className="flex-1 flex flex-col">
                  <div className="bg-green/10 text-green-800 p-4 rounded-xl mb-6 text-sm">
                    We successfully extracted the billing data from your uploaded document.
                  </div>
                    <div className="grid md:grid-cols-3 gap-4 mb-6">
                      <div className="p-4 bg-paper rounded-xl">
                        <span className="block text-xs text-muted font-bold uppercase mb-1">Bill Date</span>
                        <strong className="text-xl text-ink">{result.extracted_date || "Unknown"}</strong>
                      </div>
                      <div className="p-4 bg-paper rounded-xl">
                        <span className="block text-xs text-muted font-bold uppercase mb-1">Extracted Cost</span>
                        <strong className="text-xl text-ink">₹{result.extracted_cost?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong>
                      </div>
                      <div className="p-4 bg-paper rounded-xl">
                        <span className="block text-xs text-muted font-bold uppercase mb-1">Consumption</span>
                        <strong className="text-xl text-brand-accent">{result.extracted_consumption?.toLocaleString()} kWh</strong>
                      </div>
                    </div>

                  <button 
                    onClick={() => router.push("/dashboard")}
                    className="mt-auto w-full py-4 rounded-xl bg-green hover:bg-brand-accent text-white font-bold transition-colors flex items-center justify-center gap-2"
                  >
                    View Dashboard <ArrowRight size={18} />
                  </button>
                </div>
              )}

              {!result.valid && (
                <div className="bg-red/5 p-4 rounded-xl text-red text-sm border border-red/20 flex-1">
                  <ul className="list-disc pl-4 space-y-2">
                    {result.errors?.map((err, i) => <li key={i}>{err}</li>)}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Shell>
  );
}

function PipelineStep({ label, active, done }: { label: string, active: boolean, done: boolean }) {
  return (
    <div className={`flex items-center gap-3 p-3 rounded-xl transition-colors ${active ? (done ? 'text-green bg-green/5' : 'text-brand-dark bg-paper font-bold') : 'text-muted opacity-50'}`}>
      {done ? <CheckCircle2 size={18} className="text-green" /> : (active ? <Loader2 size={18} className="animate-spin text-brand-accent" /> : <div className="w-[18px] h-[18px] rounded-full border-2 border-line"></div>)}
      {label}
    </div>
  );
}

function StatusBadge({ valid, label }: { valid: boolean, label: string }) {
  return (
    <div className={`flex items-center gap-2 p-2 px-3 rounded-lg border text-sm font-medium ${valid ? 'bg-green/5 border-green/20 text-green' : 'bg-amber/5 border-amber/20 text-amber'}`}>
      {valid ? <CheckCircle2 size={16} /> : <AlertCircle size={16} />}
      {label}
    </div>
  );
}
