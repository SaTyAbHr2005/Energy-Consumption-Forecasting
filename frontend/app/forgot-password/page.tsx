"use client";

import { useState } from "react";
import Link from "next/link";
import { Zap, Loader2, AlertCircle } from "lucide-react";
import { createClient } from "@/utils/supabase/client";

export default function ForgotPasswordPage() {
  const supabase = createClient();
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const { error: authError } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      });

      if (authError) throw authError;

      setSuccess(true);
    } catch (err: any) {
      setError(err.message || "An error occurred. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen bg-paper flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white rounded-3xl shadow-sm border border-line p-8 md:p-10 text-center">
          <div className="w-16 h-16 bg-blue/10 text-blue rounded-full flex items-center justify-center mx-auto mb-6">
            <Zap className="w-8 h-8" />
          </div>
          <h2 className="text-2xl font-bold text-brand-dark mb-4">Check your email</h2>
          <p className="text-muted mb-8">
            If an account exists for <strong>{email}</strong>, you will receive instructions to reset your password.
          </p>
          <Link href="/login" className="bg-brand-dark text-white font-bold rounded-xl py-3.5 px-6 inline-block hover:bg-ink transition-colors">
            Return to login
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-3xl shadow-sm border border-line p-8 md:p-10">
          <div className="flex justify-center mb-6">
            <div className="w-12 h-12 bg-brand-dark rounded-xl flex items-center justify-center">
              <Zap className="text-brand-accent w-6 h-6" />
            </div>
          </div>
          
          <h1 className="text-2xl font-bold text-center text-brand-dark tracking-tight mb-2">
            Reset Password
          </h1>
          <p className="text-center text-muted mb-8">
            Enter your email to receive a reset link
          </p>

          {error && (
            <div className="bg-red/10 border border-red/20 text-red p-4 rounded-xl mb-6 flex gap-3 text-sm font-medium">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <form onSubmit={handleReset} className="space-y-5">
            <div>
              <label className="block text-sm font-bold text-ink mb-1.5" htmlFor="email">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                className="w-full px-4 py-3 rounded-xl border border-line bg-paper/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-accent/50 focus:border-brand-accent transition-all text-ink placeholder-muted/50"
                placeholder="name@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-dark text-white font-bold rounded-xl py-3.5 px-4 hover:bg-ink transition-colors flex items-center justify-center gap-2 mt-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Send Reset Link"}
            </button>
          </form>

          <div className="mt-8 text-center text-sm text-muted">
            Remember your password?{" "}
            <Link href="/login" className="text-brand-dark font-bold hover:underline">
              Sign in
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
