"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Zap, Loader2, AlertCircle } from "lucide-react";
import { createClient } from "@/utils/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const supabase = createClient();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      console.log("Attempting sign in for:", email);
      const { data, error: authError } = await supabase.auth.signInWithPassword({
        email,
        password,
      });

      console.log("Sign in result:", { data, authError });

      if (authError) throw authError;

      console.log("Sign in successful, pushing to /dashboard");
      router.push("/dashboard");
      router.refresh();
    } catch (err: any) {
      console.error("Login catch block hit:", err);
      setError(err.message || "Unable to sign in. Please check your credentials.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-paper flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="bg-white rounded-3xl shadow-sm border border-line p-8 md:p-10">
          <div className="flex justify-center mb-8">
            <div className="w-12 h-12 bg-brand-dark rounded-xl flex items-center justify-center">
              <Zap className="text-brand-accent w-6 h-6" />
            </div>
          </div>
          
          <h1 className="text-2xl font-bold text-center text-brand-dark tracking-tight mb-2">
            Welcome back
          </h1>
          <p className="text-center text-muted mb-8">
            Sign in to your EnergySense account
          </p>

          {error && (
            <div className="bg-red/10 border border-red/20 text-red p-4 rounded-xl mb-6 flex gap-3 text-sm font-medium">
              <AlertCircle className="w-5 h-5 shrink-0" />
              <p>{error}</p>
            </div>
          )}

          <form onSubmit={handleLogin} className="space-y-5">
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

            <div>
              <div className="flex justify-between items-center mb-1.5">
                <label className="block text-sm font-bold text-ink" htmlFor="password">
                  Password
                </label>
                <Link href="/forgot-password" className="text-sm text-brand-accent font-medium hover:underline">
                  Forgot password?
                </Link>
              </div>
              <input
                id="password"
                type="password"
                required
                className="w-full px-4 py-3 rounded-xl border border-line bg-paper/50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-accent/50 focus:border-brand-accent transition-all text-ink placeholder-muted/50"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-brand-dark text-white font-bold rounded-xl py-3.5 px-4 hover:bg-ink transition-colors flex items-center justify-center gap-2 mt-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "Sign In"}
            </button>
          </form>

          <div className="mt-8 text-center text-sm text-muted">
            Don't have an account?{" "}
            <Link href="/register" className="text-brand-dark font-bold hover:underline">
              Create one
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
