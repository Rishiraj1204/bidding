"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, ArrowRight, Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { loginApi } from "@/lib/api";

const DEMO_ROLES = [
  { label: "Administrator", email: "admin@gem.gov.in", accent: "border-purple-500/30 text-purple-300 hover:bg-purple-500/10" },
  { label: "Procurement Officer", email: "officer@gem.gov.in", accent: "border-blue-500/30 text-blue-300 hover:bg-blue-500/10" },
  { label: "Bidder / Vendor", email: "bidder@vendor.in", accent: "border-emerald-500/30 text-emerald-300 hover:bg-emerald-500/10" },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const result = await loginApi(email, password);
      localStorage.setItem("token", result.access_token);
      localStorage.setItem("user_email", result.user.email);
      localStorage.setItem("user_role", result.user.roles[0] || "");
      router.push("/dashboard");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Unable to sign in. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-10 text-slate-100 sm:flex sm:items-center sm:justify-center">
      <section className="w-full max-w-md rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl sm:p-8">
        <Link href="/" className="mb-8 inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400">
          <ShieldCheck className="h-4 w-4" /> BIDVERIFY AI
        </Link>
        <div className="mb-6 space-y-2">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400">
            <LockKeyhole className="h-5 w-5" />
          </div>
          <h1 className="text-2xl font-bold text-white">Sign in to your workspace</h1>
          <p className="text-sm text-slate-400">Use the credentials assigned to your BIDVERIFY account.</p>
        </div>

        {error && <div className="mb-4 flex gap-2 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300"><AlertCircle className="h-4 w-4 shrink-0" />{error}</div>}

        <form onSubmit={handleSubmit} className="space-y-4">
          <label className="block space-y-1.5 text-xs font-semibold text-slate-300">Email address
            <input type="email" required autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm font-normal text-white outline-none focus:border-emerald-500" />
          </label>
          <label className="block space-y-1.5 text-xs font-semibold text-slate-300">Password
            <span className="relative block"><input type={showPassword ? "text" : "password"} required autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2.5 pr-10 text-sm font-normal text-white outline-none focus:border-emerald-500" /><button type="button" onClick={() => setShowPassword((shown) => !shown)} className="absolute right-3 top-3 text-slate-500 hover:text-slate-300" aria-label="Toggle password visibility">{showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}</button></span>
          </label>
          <button type="submit" disabled={loading} className="flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-bold text-white hover:bg-emerald-500 disabled:opacity-60">{loading ? "Signing in..." : <>Sign in <ArrowRight className="h-4 w-4" /></>}</button>
        </form>

        <div className="mt-6 border-t border-slate-800 pt-5">
          <p className="mb-3 text-xs font-semibold text-slate-400">Demo role access</p>
          <div className="grid gap-2 sm:grid-cols-3">
            {DEMO_ROLES.map((role) => (
              <button key={role.email} type="button" onClick={() => { setEmail(role.email); setPassword("DemoPass123!"); }} className={`rounded-lg border px-2 py-2 text-[11px] font-semibold transition-colors ${role.accent}`}>
                {role.label}
              </button>
            ))}
          </div>
          <p className="mt-3 text-center text-[11px] text-slate-500">Select a role to fill its demo credentials, then sign in.</p>
        </div>
      </section>
    </main>
  );
}
