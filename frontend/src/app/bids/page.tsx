"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import {
  Send,
  PlusCircle,
  Building2,
  Calendar,
  Layers,
  ArrowRight,
  Filter,
  RefreshCw,
  AlertCircle,
  Clock,
  CheckCircle2,
  XCircle,
  FileText,
  FileCheck,
} from "lucide-react";
import { fetchBids, BidItem, fetchCurrentUserApi } from "@/lib/api";

const BID_STATUS_FILTERS = [
  { label: "All Bids", value: "ALL" },
  { label: "Draft", value: "DRAFT" },
  { label: "Submitted", value: "SUBMITTED" },
  { label: "Under Review", value: "UNDER_REVIEW" },
  { label: "Compliant", value: "COMPLIANT" },
  { label: "Withdrawn", value: "WITHDRAWN" },
];

export default function BidsPage() {
  const [bids, setBids] = useState<BidItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    setToken(sessionToken);
    loadBids(sessionToken);
    if (sessionToken) {
      fetchCurrentUserApi(sessionToken)
        .then((user) => setRole(user.roles[0] || ""))
        .catch(() => setRole(""));
    }
  }, []);

  const canCreateBids = role === "ADMIN" || role === "BIDDER";

  async function loadBids(authToken: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBids({
        status: statusFilter,
        token: authToken || token,
      });
      setBids(data.items);
    } catch (err: any) {
      setError(err.message || "Failed to load bids");
    } finally {
      setLoading(false);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "SUBMITTED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-2.5 py-1 text-xs font-semibold text-blue-400 border border-blue-500/20">
            <CheckCircle2 className="h-3 w-3" /> Submitted
          </span>
        );
      case "DRAFT":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-2.5 py-1 text-xs font-semibold text-amber-400 border border-amber-500/20">
            <Clock className="h-3 w-3" /> Draft
          </span>
        );
      case "UNDER_REVIEW":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 px-2.5 py-1 text-xs font-semibold text-purple-400 border border-purple-500/20">
            <RefreshCw className="h-3 w-3 animate-spin" /> Under Review
          </span>
        );
      case "COMPLIANT":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <FileCheck className="h-3 w-3" /> Compliant
          </span>
        );
      case "WITHDRAWN":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-500/10 px-2.5 py-1 text-xs font-semibold text-slate-400 border border-slate-500/20">
            <XCircle className="h-3 w-3" /> Withdrawn
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-800 px-2.5 py-1 text-xs font-medium text-slate-400 border border-slate-700">
            {status}
          </span>
        );
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Top Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div>
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white flex items-center gap-3">
              <Send className="h-8 w-8 text-emerald-400" />
              Bid Submissions & Submissions Workspace
            </h1>
            <p className="mt-1 text-sm text-slate-400">
              Manage draft bids, submit compliance packages, and track evaluation status in real-time.
            </p>
          </div>
          {canCreateBids && (
            <Link
              href="/bids/new"
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 hover:from-emerald-500 hover:to-teal-400 transition-all active:scale-95"
            >
              <PlusCircle className="h-4 w-4" />
              Start New Bid
            </Link>
          )}
        </div>

        {/* Filter Bar */}
        <div className="mt-6 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 font-medium flex items-center gap-1 mr-1">
              <Filter className="h-3.5 w-3.5" /> Status:
            </span>
            {BID_STATUS_FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => {
                  setStatusFilter(f.value);
                  setTimeout(() => loadBids(token), 10);
                }}
                className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                  statusFilter === f.value
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                    : "bg-slate-900 text-slate-400 border border-slate-800 hover:bg-slate-800 hover:text-slate-200"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>

          <button
            onClick={() => loadBids(token)}
            title="Refresh submissions"
            className="rounded-lg p-2 bg-slate-900 border border-slate-800 text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-all"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mt-6 flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            <p>{error}</p>
          </div>
        )}

        {/* Bids Grid */}
        <div className="mt-6">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 animate-pulse space-y-4"
                >
                  <div className="h-4 w-28 bg-slate-800 rounded"></div>
                  <div className="h-6 w-4/5 bg-slate-800 rounded"></div>
                  <div className="h-4 w-1/2 bg-slate-800 rounded"></div>
                </div>
              ))}
            </div>
          ) : bids.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-slate-800/80 text-slate-400 mb-4">
                <FileText className="h-7 w-7" />
              </div>
              <h3 className="text-lg font-semibold text-slate-200">No bid submissions found</h3>
              <p className="mt-1 text-sm text-slate-400 max-w-sm">
                You currently have no active or draft bids matching this status. Explore open tenders and submit your first bid.
              </p>
              <Link
                href="/tenders"
                className="mt-5 inline-flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-500 transition-colors"
              >
                Browse Open Tenders
              </Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {bids.map((bid) => (
                <div
                  key={bid.id}
                  className="group flex flex-col justify-between rounded-2xl border border-slate-800/80 bg-slate-900/70 p-6 hover:border-slate-700 hover:bg-slate-900 transition-all hover:shadow-xl hover:shadow-emerald-950/20"
                >
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs font-semibold text-emerald-400/90 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                        {bid.bid_number}
                      </span>
                      {getStatusBadge(bid.status)}
                    </div>

                    <h3 className="font-semibold text-slate-100 group-hover:text-emerald-300 transition-colors line-clamp-2">
                      {bid.tender_title || "Procurement Bid Submission"}
                    </h3>

                    <div className="space-y-1.5 text-xs text-slate-400">
                      {bid.tender_number && (
                        <div className="flex items-center gap-2">
                          <FileText className="h-3.5 w-3.5 text-slate-500" />
                          <span className="font-mono text-slate-300">Tender #{bid.tender_number}</span>
                        </div>
                      )}
                      {bid.tender_organization && (
                        <div className="flex items-center gap-2">
                          <Building2 className="h-3.5 w-3.5 text-slate-500" />
                          <span className="truncate">{bid.tender_organization}</span>
                        </div>
                      )}
                      {bid.submission_date ? (
                        <div className="flex items-center gap-2 text-blue-400 font-medium">
                          <Calendar className="h-3.5 w-3.5" />
                          <span>Submitted: {new Date(bid.submission_date).toLocaleDateString()}</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-amber-400/90 font-medium">
                          <Clock className="h-3.5 w-3.5" />
                          <span>Status: Draft (Pending Submission)</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="mt-6 pt-4 border-t border-slate-800/60 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs text-slate-400">
                      <span>{bid.documents_count} Files Attached</span>
                    </div>

                    <Link
                      href={`/bids/${bid.id}`}
                      className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 group-hover:translate-x-1 transition-transform"
                    >
                      View Bid <ArrowRight className="h-3.5 w-3.5" />
                    </Link>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
