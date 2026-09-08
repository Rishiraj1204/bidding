"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  LayoutDashboard,
  ShieldCheck,
  FileText,
  Send,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  PlusCircle,
  History,
  Users,
  BrainCircuit,
  FileCheck,
  ArrowRight,
  TrendingUp,
} from "lucide-react";
import { fetchDashboardSummaryApi, DashboardSummaryResponse } from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [summary, setSummary] = useState<DashboardSummaryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      const storedToken = localStorage.getItem("token");
      if (!storedToken) {
        router.replace("/login");
        return;
      }
      setToken(storedToken);
      loadDashboard(storedToken);
    }
    init();
  }, [router]);

  async function loadDashboard(authToken: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchDashboardSummaryApi(authToken || token);
      setSummary(data);
    } catch (err: any) {
      setError(err.message || "Failed to load dashboard metrics.");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex items-center justify-center p-6">
        <div className="text-center space-y-3">
          <RefreshCw className="h-8 w-8 animate-spin text-emerald-400 mx-auto" />
          <p className="text-sm font-medium text-slate-300">Loading Operational Dashboard...</p>
        </div>
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 p-6 sm:p-8 flex items-center justify-center">
        <div className="max-w-md w-full rounded-2xl border border-rose-500/20 bg-rose-500/5 p-6 text-center space-y-4">
          <AlertCircle className="h-8 w-8 text-rose-400 mx-auto" />
          <h3 className="text-base font-bold text-white">Unable to Load Dashboard</h3>
          <p className="text-xs text-slate-400">{error || "No data received."}</p>
          <button
            onClick={() => loadDashboard(token)}
            className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-white hover:bg-slate-700"
          >
            Retry Connection
          </button>
        </div>
      </div>
    );
  }

  const roleLabels: Record<string, string> = {
    ADMIN: "System Administrator",
    PROCUREMENT_OFFICER: "Procurement Officer",
    BIDDER: "Verified Vendor / Bidder",
    REVIEWER: "Technical Review Committee",
    AUDITOR: "Statutory Auditor",
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Header & Role Badge Banner */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 rounded-3xl border border-slate-800 bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 p-6 sm:p-8 shadow-2xl">
          <div className="space-y-1.5">
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                Welcome, {summary.user_name}
              </h1>
              <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-3 py-1 text-xs font-bold text-emerald-400">
                {roleLabels[summary.role] || summary.role}
              </span>
            </div>
            <p className="text-xs sm:text-sm text-slate-400">
              Operational compliance dashboard, AI verification statistics, and task workflows.
            </p>
          </div>

          {/* Quick Actions */}
          <div className="flex items-center gap-2 sm:gap-3 flex-wrap">
            {(summary.role === "ADMIN" || summary.role === "PROCUREMENT_OFFICER") && (
              <Link
                href="/tenders/new"
                className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-500/20 hover:from-emerald-500 hover:to-teal-400 transition-all"
              >
                <PlusCircle className="h-4 w-4" /> Create Tender
              </Link>
            )}
            <Link
              href="/tenders"
              className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-all"
            >
              <FileText className="h-4 w-4 text-indigo-400" /> {summary.role === "PROCUREMENT_OFFICER" ? "Manage Tenders" : "Explore Tenders"}
            </Link>
            {summary.role === "BIDDER" && (
              <Link href="/bids/new" className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-500/20 hover:from-emerald-500 hover:to-teal-400 transition-all">
                <Send className="h-4 w-4" /> Submit Bid
              </Link>
            )}
            {(summary.role === "ADMIN" || summary.role === "AUDITOR") && (
              <Link
                href="/audit-logs"
                className="inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-800/80 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800 transition-all"
              >
                <History className="h-4 w-4 text-amber-400" /> Audit Trail
              </Link>
            )}
          </div>
        </div>

        {/* Dynamic Role Metrics KPI Grid */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6">
          {Object.entries(summary.metrics).map(([key, value]) => {
            const formattedKey = key
              .replace(/_/g, " ")
              .replace(/\b\w/g, (l) => l.toUpperCase());

            return (
              <div
                key={key}
                className="group relative rounded-2xl border border-slate-800 bg-slate-900/60 p-5 space-y-2 hover:border-slate-700 transition-all shadow-lg"
              >
                <div className="flex items-center justify-between text-slate-400 text-xs font-medium">
                  <span>{formattedKey}</span>
                  <TrendingUp className="h-4 w-4 text-emerald-400/60 group-hover:text-emerald-400 transition-colors" />
                </div>
                <div className="text-2xl sm:text-3xl font-extrabold text-white font-mono tracking-tight">
                  {typeof value === "number" ? value.toLocaleString() : String(value)}
                </div>
              </div>
            );
          })}
        </div>

        {/* Content Section: 2 Columns */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Column: Recent Bids & Tenders (2/3 width) */}
          <div className="lg:col-span-2 space-y-8">
            {/* Recent Bids Table */}
            {summary.recent_bids && summary.recent_bids.length > 0 && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Send className="h-5 w-5 text-teal-400" />
                    <h2 className="text-base font-bold text-white">Recent Bid Submissions</h2>
                  </div>
                  <Link
                    href="/bids"
                    className="text-xs font-semibold text-teal-400 hover:text-teal-300 flex items-center gap-1"
                  >
                    View All <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3">Bid Number</th>
                        <th className="px-4 py-3">Tender</th>
                        <th className="px-4 py-3">Status</th>
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {summary.recent_bids.map((b: any) => (
                        <tr key={b.id} className="hover:bg-slate-800/30 transition-colors">
                          <td className="px-4 py-3 font-semibold text-white">{b.bid_number}</td>
                          <td className="px-4 py-3 text-slate-300 font-sans truncate max-w-[200px]">
                            {b.tender_title || "General Tender"}
                          </td>
                          <td className="px-4 py-3">
                            <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-[10px] font-semibold text-slate-300 border border-slate-700">
                              {b.status}
                            </span>
                          </td>
                          <td className="px-4 py-3 text-right font-sans">
                            <Link
                              href={`/bids/${b.id}`}
                              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                            >
                              Inspect <ArrowRight className="h-3 w-3" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* Recent Tenders Table */}
            {summary.recent_tenders && summary.recent_tenders.length > 0 && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <FileText className="h-5 w-5 text-indigo-400" />
                    <h2 className="text-base font-bold text-white">Active Tender Opportunities</h2>
                  </div>
                  <Link
                    href="/tenders"
                    className="text-xs font-semibold text-indigo-400 hover:text-indigo-300 flex items-center gap-1"
                  >
                    View All <ArrowRight className="h-3 w-3" />
                  </Link>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs text-slate-300">
                    <thead className="bg-slate-950 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                      <tr>
                        <th className="px-4 py-3">Tender Ref</th>
                        <th className="px-4 py-3">Title</th>
                        <th className="px-4 py-3 text-right">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60 font-mono">
                      {summary.recent_tenders.map((t: any) => (
                        <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                          <td className="px-4 py-3 font-semibold text-white">{t.tender_number}</td>
                          <td className="px-4 py-3 text-slate-300 font-sans truncate max-w-[240px]">
                            {t.title}
                          </td>
                          <td className="px-4 py-3 text-right font-sans">
                            <Link
                              href={`/tenders/${t.id}`}
                              className="inline-flex items-center gap-1 text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                            >
                              Details <ArrowRight className="h-3 w-3" />
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Side Column: Review Tasks / Recent Audit Activity (1/3 width) */}
          <div className="space-y-8">
            {/* Review Tasks Queue */}
            {summary.pending_tasks && summary.pending_tasks.length > 0 && (
              <div className="rounded-2xl border border-amber-500/20 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center gap-2">
                  <BrainCircuit className="h-5 w-5 text-amber-400" />
                  <h2 className="text-base font-bold text-white">Pending Review Queue</h2>
                </div>

                <div className="space-y-3">
                  {summary.pending_tasks.map((task: any) => (
                    <div
                      key={task.id}
                      className="rounded-xl border border-slate-800 bg-slate-950 p-3.5 space-y-2 text-xs"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[10px] text-slate-400 font-semibold">
                          Bid #{task.bid_number || task.bid_id?.substring(0, 8)}
                        </span>
                        <span className="rounded bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 text-[9px] font-bold text-amber-300">
                          {task.status}
                        </span>
                      </div>
                      <p className="text-slate-300 text-[11px] leading-relaxed line-clamp-2">
                        {task.requirement_text || task.trigger_reason}
                      </p>
                      <div className="flex items-center justify-end pt-1">
                        <Link
                          href={`/bids/${task.bid_id}`}
                          className="text-[11px] font-semibold text-indigo-400 hover:underline"
                        >
                          Open Review &rarr;
                        </Link>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Recent Audit Activity Feed */}
            {summary.recent_activity && summary.recent_activity.length > 0 && (
              <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <History className="h-5 w-5 text-indigo-400" />
                    <h2 className="text-base font-bold text-white">Recent Audit Events</h2>
                  </div>
                  <Link
                    href="/audit-logs"
                    className="text-xs font-semibold text-indigo-400 hover:text-indigo-300"
                  >
                    All Logs
                  </Link>
                </div>

                <div className="space-y-3 divide-y divide-slate-800/60">
                  {summary.recent_activity.map((act: any) => (
                    <div key={act.id} className="pt-2.5 space-y-1 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-mono text-[11px] font-bold text-white">
                          {act.action}
                        </span>
                        <span className="text-[10px] text-slate-500 font-mono">
                          {new Date(act.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <p className="text-[11px] text-slate-400 truncate">
                        By: <span className="text-slate-300">{act.actor_email || "System"}</span> • Type: {act.resource_type}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
