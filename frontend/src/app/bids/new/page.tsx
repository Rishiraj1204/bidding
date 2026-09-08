"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import {
  Send,
  ArrowLeft,
  Building2,
  Calendar,
  Layers,
  CheckCircle,
  AlertCircle,
  Clock,
  FileText,
} from "lucide-react";
import { createBidApi, fetchCurrentUserApi, fetchTenders, TenderItem } from "@/lib/api";

function NewBidForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialTenderId = searchParams.get("tender_id") || "";

  const [tenders, setTenders] = useState<TenderItem[]>([]);
  const [selectedTenderId, setSelectedTenderId] = useState(initialTenderId);
  const [notes, setNotes] = useState("");
  const [bidNumber, setBidNumber] = useState(`BID/${new Date().getFullYear()}/${Math.floor(10000 + Math.random() * 90000)}`);
  
  const [loading, setLoading] = useState(false);
  const [loadingTenders, setLoadingTenders] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [token, setToken] = useState("");

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    if (!sessionToken) {
      router.replace("/login");
      return;
    }
    fetchCurrentUserApi(sessionToken)
      .then((user) => {
        if (!user.roles.includes("ADMIN") && !user.roles.includes("BIDDER")) {
          router.replace("/dashboard");
          return;
        }
        setToken(sessionToken);
        loadTenders(sessionToken);
      })
      .catch(() => router.replace("/login"));
  }, [router]);

  async function loadTenders(authToken: string) {
    setLoadingTenders(true);
    try {
      const data = await fetchTenders({
        status: "PUBLISHED",
        token: authToken || token,
      });
      setTenders(data.items);
      if (!selectedTenderId && data.items.length > 0) {
        setSelectedTenderId(data.items[0].id);
      }
    } catch {
    } finally {
      setLoadingTenders(false);
    }
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedTenderId) {
      setError("Please select an active published tender to submit a bid against.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const res = await createBidApi(
        {
          tender_id: selectedTenderId,
          bid_number: bidNumber,
          notes: notes || undefined,
        },
        token
      );
      router.push(`/bids/${res.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create bid. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  const selectedTender = tenders.find((t) => t.id === selectedTenderId);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation />

      <main className="flex-1 mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Back Link */}
        <Link
          href="/bids"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" /> Back to My Bids
        </Link>

        {/* Header */}
        <div className="border-b border-slate-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <Send className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Create Bid Submission</h1>
              <p className="mt-0.5 text-xs text-slate-400">Initialize a compliant bid draft against an active published tender.</p>
            </div>
          </div>
        </div>

        {/* Error Alert */}
        {error && (
          <div className="mt-6 flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            <p>{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 space-y-6">
            {/* Tender Selection */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Target Published Tender *
              </label>
              {loadingTenders ? (
                <div className="h-10 w-full bg-slate-800 rounded-xl animate-pulse"></div>
              ) : tenders.length === 0 ? (
                <div className="rounded-xl border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-300">
                  No published tenders are currently accepting submissions.
                </div>
              ) : (
                <select
                  required
                  value={selectedTenderId}
                  onChange={(e) => setSelectedTenderId(e.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
                >
                  {tenders.map((t) => (
                    <option key={t.id} value={t.id}>
                      [{t.tender_number}] {t.title} — {t.organization}
                    </option>
                  ))}
                </select>
              )}
            </div>

            {/* Selected Tender Card Preview */}
            {selectedTender && (
              <div className="rounded-xl border border-slate-800 bg-slate-950/80 p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs text-emerald-400 font-semibold">{selectedTender.tender_number}</span>
                  <span className="text-xs text-amber-400 flex items-center gap-1 font-medium">
                    <Clock className="h-3.5 w-3.5" /> Deadline: {new Date(selectedTender.submission_deadline).toLocaleString()}
                  </span>
                </div>
                <h4 className="text-sm font-semibold text-slate-200">{selectedTender.title}</h4>
                <div className="flex items-center gap-4 text-xs text-slate-400">
                  <span className="flex items-center gap-1">
                    <Building2 className="h-3.5 w-3.5 text-slate-500" />
                    {selectedTender.organization}
                  </span>
                  {selectedTender.category && (
                    <span className="flex items-center gap-1">
                      <Layers className="h-3.5 w-3.5 text-slate-500" />
                      {selectedTender.category}
                    </span>
                  )}
                </div>
              </div>
            )}

            {/* Bid Identifier */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Bid Reference Number *
              </label>
              <input
                type="text"
                required
                value={bidNumber}
                onChange={(e) => setBidNumber(e.target.value)}
                placeholder="e.g. BID/2026/10492"
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm font-mono text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
              />
            </div>

            {/* Bid Notes / Technical Remarks */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Commercial Summary & Bidder Remarks
              </label>
              <textarea
                rows={4}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Provide initial executive summary, authorized signatory notes, or delivery timeline commitments..."
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
              />
            </div>
          </div>

          {/* Submit Action */}
          <div className="flex items-center justify-end gap-3">
            <Link
              href="/bids"
              className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-2.5 text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={loading || tenders.length === 0}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 hover:from-emerald-500 hover:to-teal-400 transition-all disabled:opacity-50"
            >
              {loading ? (
                <span>Initializing Bid...</span>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Initialize Bid Draft
                </>
              )}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}

export default function NewBidPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-slate-950 text-slate-400 flex items-center justify-center">Loading...</div>}>
      <NewBidForm />
    </Suspense>
  );
}
