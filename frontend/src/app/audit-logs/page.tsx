"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  History,
  ShieldCheck,
  Search,
  Filter,
  RefreshCw,
  AlertCircle,
  Eye,
  X,
  ChevronLeft,
  ChevronRight,
  ShieldAlert,
} from "lucide-react";
import { fetchAuditLogsApi, AuditLogItem } from "@/lib/api";

export default function AuditLogsPage() {
  const [token, setToken] = useState("");
  const [logs, setLogs] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(15);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [actionFilter, setActionFilter] = useState("");
  const [actorFilter, setActorFilter] = useState("");
  const [resourceTypeFilter, setResourceTypeFilter] = useState("");

  // Inspect Modal
  const [selectedLog, setSelectedLog] = useState<AuditLogItem | null>(null);

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    setToken(sessionToken);
    loadLogs(sessionToken, 1);
  }, []);

  async function loadLogs(authToken: string, targetPage: number) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchAuditLogsApi(authToken || token, {
        page: targetPage,
        page_size: pageSize,
        action: actionFilter.trim() || undefined,
        actor_email: actorFilter.trim() || undefined,
        resource_type: resourceTypeFilter.trim() || undefined,
      });
      setLogs(data.items);
      setTotal(data.total);
      setPage(data.page);
    } catch (err: any) {
      setError(err.message || "Failed to load audit logs.");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    loadLogs(token, 1);
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <History className="h-6 w-6 text-amber-400" />
              <h1 className="text-2xl font-bold tracking-tight text-white">System Audit & Compliance Log</h1>
              <span className="rounded-full bg-amber-500/10 border border-amber-500/20 px-2.5 py-0.5 text-xs font-semibold text-amber-300">
                Immutable Trail
              </span>
            </div>
            <p className="text-xs text-slate-400">
              Tamper-evident record of all authentication, tender modifications, bid evaluations, overrides, and report events.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={() => loadLogs(token, page)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Security Notice */}
        <div className="rounded-2xl border border-indigo-500/20 bg-indigo-500/5 p-4 flex items-start gap-3 text-xs text-indigo-300">
          <ShieldAlert className="h-4 w-4 shrink-0 text-indigo-400 mt-0.5" />
          <p>
            <b>Security & Privacy Guarantee:</b> All password hashes, JWT tokens, and sensitive secret keys are automatically sanitized and redacted server-side before persisting in the audit catalog.
          </p>
        </div>

        {/* Filters Form */}
        <form onSubmit={handleSearch} className="rounded-2xl border border-slate-800 bg-slate-900/60 p-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
            <div>
              <label className="text-slate-400 font-semibold block mb-1">Actor Email</label>
              <input
                type="text"
                placeholder="e.g. officer@gem.gov.in"
                value={actorFilter}
                onChange={(e) => setActorFilter(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-slate-400 font-semibold block mb-1">Action Name</label>
              <input
                type="text"
                placeholder="e.g. REVIEW_OVERRIDE, BID_SUBMITTED"
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <div>
              <label className="text-slate-400 font-semibold block mb-1">Resource Type</label>
              <input
                type="text"
                placeholder="e.g. tender, bid, review_task"
                value={resourceTypeFilter}
                onChange={(e) => setResourceTypeFilter(e.target.value)}
                className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
            <button
              type="button"
              onClick={() => {
                setActionFilter("");
                setActorFilter("");
                setResourceTypeFilter("");
                loadLogs(token, 1);
              }}
              className="rounded-xl bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700"
            >
              Reset Filters
            </button>
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-1.5 text-xs font-semibold text-white shadow-lg shadow-indigo-500/20 hover:from-indigo-500 hover:to-purple-500"
            >
              <Search className="h-3.5 w-3.5" /> Apply Filters
            </button>
          </div>
        </form>

        {/* Logs Table */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 overflow-hidden shadow-xl">
          {loading ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <RefreshCw className="h-6 w-6 animate-spin text-indigo-400 mx-auto" />
              <p className="text-xs">Fetching audit trail entries...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center text-rose-400 space-y-2">
              <AlertCircle className="h-6 w-6 mx-auto" />
              <p className="text-xs font-semibold">{error}</p>
            </div>
          ) : logs.length === 0 ? (
            <div className="p-12 text-center text-slate-500 space-y-2">
              <History className="h-8 w-8 mx-auto text-slate-600" />
              <p className="text-sm font-semibold text-slate-400">No audit events match your filters.</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Actor Email</th>
                    <th className="px-4 py-3">Resource Type</th>
                    <th className="px-4 py-3">Resource ID</th>
                    <th className="px-4 py-3 text-right">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {logs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 text-slate-400 whitespace-nowrap">
                        {new Date(log.timestamp).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 font-bold text-white">
                        <span className="rounded bg-indigo-500/10 px-2 py-0.5 text-[11px] text-indigo-300 border border-indigo-500/20">
                          {log.action}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-sans text-slate-300 truncate max-w-[200px]">
                        {log.actor_email || "System"}
                      </td>
                      <td className="px-4 py-3 uppercase text-[10px] text-slate-400">
                        {log.resource_type}
                      </td>
                      <td className="px-4 py-3 text-slate-500 text-[11px]">
                        {log.resource_id ? `${log.resource_id.substring(0, 8)}...` : "—"}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        <button
                          onClick={() => setSelectedLog(log)}
                          className="inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
                        >
                          <Eye className="h-3.5 w-3.5" /> Inspect
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Footer */}
          {!loading && logs.length > 0 && (
            <div className="flex items-center justify-between p-4 border-t border-slate-800 bg-slate-950/60 text-xs text-slate-400">
              <span>
                Showing page <b>{page}</b> of <b>{totalPages}</b> ({total} total entries)
              </span>
              <div className="flex items-center gap-2">
                <button
                  disabled={page <= 1}
                  onClick={() => loadLogs(token, page - 1)}
                  className="inline-flex items-center gap-1 rounded-xl bg-slate-800 px-3 py-1.5 font-semibold text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                >
                  <ChevronLeft className="h-3.5 w-3.5" /> Previous
                </button>
                <button
                  disabled={page >= totalPages}
                  onClick={() => loadLogs(token, page + 1)}
                  className="inline-flex items-center gap-1 rounded-xl bg-slate-800 px-3 py-1.5 font-semibold text-slate-300 hover:bg-slate-700 disabled:opacity-50"
                >
                  Next <ChevronRight className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Inspect State Modal */}
      {selectedLog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden space-y-4">
            <div className="flex items-center justify-between p-4 border-b border-slate-800 bg-slate-950/60">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-amber-400" />
                <h3 className="text-sm font-bold text-white">Audit Event: {selectedLog.action}</h3>
              </div>
              <button onClick={() => setSelectedLog(null)} className="text-slate-400 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="p-4 space-y-4 max-h-[70vh] overflow-y-auto text-xs font-mono">
              <div className="grid grid-cols-2 gap-3 text-[11px] font-sans">
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block">Actor</span>
                  <span className="text-white font-medium">{selectedLog.actor_email || "System"}</span>
                </div>
                <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
                  <span className="text-[10px] text-slate-500 uppercase block">Timestamp</span>
                  <span className="text-white font-medium">{new Date(selectedLog.timestamp).toLocaleString()}</span>
                </div>
              </div>

              {selectedLog.new_state && (
                <div className="space-y-1">
                  <label className="text-slate-300 font-sans font-semibold text-xs">New State Payload</label>
                  <pre className="rounded-xl border border-slate-800 bg-slate-950 p-3.5 text-indigo-300 text-[11px] overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedLog.new_state, null, 2)}
                  </pre>
                </div>
              )}

              {selectedLog.previous_state && (
                <div className="space-y-1">
                  <label className="text-slate-300 font-sans font-semibold text-xs">Previous State</label>
                  <pre className="rounded-xl border border-slate-800 bg-slate-950 p-3.5 text-slate-400 text-[11px] overflow-x-auto whitespace-pre-wrap">
                    {JSON.stringify(selectedLog.previous_state, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            <div className="flex items-center justify-end p-4 border-t border-slate-800 bg-slate-950">
              <button
                onClick={() => setSelectedLog(null)}
                className="rounded-xl bg-slate-800 px-4 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
