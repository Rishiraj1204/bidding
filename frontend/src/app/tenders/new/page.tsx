"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import {
  FileText,
  ArrowLeft,
  Building2,
  Calendar,
  Layers,
  CheckCircle,
  AlertCircle,
  Clock,
  Sparkles,
} from "lucide-react";
import { createTenderApi, fetchCurrentUserApi } from "@/lib/api";

const SAMPLE_CATEGORIES = [
  "Medical Equipment",
  "IT & Computing Hardware",
  "Cloud & Software Services",
  "Civil Infrastructure & Works",
  "Consultancy & Advisory",
  "Electrical & Power Systems",
  "Security & Surveillance",
  "Facility Management",
];

export default function NewTenderPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form Fields
  const [tenderNumber, setTenderNumber] = useState(`GEM/${new Date().getFullYear()}/B/${Math.floor(1000 + Math.random() * 9000)}`);
  const [title, setTitle] = useState("");
  const [organization, setOrganization] = useState("");
  const [category, setCategory] = useState(SAMPLE_CATEGORIES[0]);
  const [description, setDescription] = useState("");
  
  // Default deadline 14 days in the future
  const defaultDeadline = new Date(Date.now() + 14 * 24 * 60 * 60 * 1000).toISOString().slice(0, 16);
  const [submissionDeadline, setSubmissionDeadline] = useState(defaultDeadline);
  const [initialStatus, setInitialStatus] = useState<"DRAFT" | "PUBLISHED">("DRAFT");
  const [token, setToken] = useState("");
  const [accessChecked, setAccessChecked] = useState(false);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    if (!sessionToken) {
      router.replace("/login");
      setAccessChecked(true);
      return;
    }
    fetchCurrentUserApi(sessionToken)
      .then((user) => {
        if (!user.roles.includes("ADMIN") && !user.roles.includes("PROCUREMENT_OFFICER")) {
          router.replace("/dashboard");
          setAccessChecked(true);
          return;
        }
        setToken(sessionToken);
        setAuthorized(true);
        setAccessChecked(true);
      })
      .catch(() => {
        setAccessChecked(true);
        router.replace("/login");
      });
  }, [router]);

  if (!accessChecked) {
    return <div className="min-h-screen bg-slate-950" />;
  }

  if (!authorized) {
    return null;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      if (!token) {
        router.replace("/login");
        return;
      }
      if (!tenderNumber.trim() || !title.trim() || !organization.trim() || !category || !description.trim() || !submissionDeadline) {
        setError("Complete every required tender field before saving or publishing.");
        return;
      }

      const res = await createTenderApi(
        {
          tender_number: tenderNumber.trim(),
          title: title.trim(),
          organization: organization.trim(),
          category,
          description: description.trim(),
          submission_deadline: new Date(submissionDeadline).toISOString(),
          status: initialStatus,
        },
        token
      );

      // Redirect to newly created tender
      router.push(`/tenders/${res.id}`);
    } catch (err: any) {
      setError(err.message || "Failed to create tender. Please check your inputs.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation />

      <main className="flex-1 mx-auto w-full max-w-4xl px-4 py-8 sm:px-6 lg:px-8">
        {/* Back Link */}
        <Link
          href="/tenders"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors mb-6"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Tender Catalog
        </Link>

        {/* Header */}
        <div className="border-b border-slate-800 pb-6">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <FileText className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Create New Tender</h1>
              <p className="mt-0.5 text-xs text-slate-400">Step 1 of 5 — Tender Profile & Basic Specifications</p>
            </div>
          </div>
        </div>

        {/* Wizard Steps indicator */}
        <div className="mt-6 flex items-center justify-between text-xs font-medium border border-slate-800 bg-slate-900/60 rounded-xl p-3">
          <span className="text-emerald-400 flex items-center gap-1.5 font-semibold">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 text-[10px]">1</span>
            Basic Details
          </span>
          <span className="text-slate-600">→</span>
          <span className="text-slate-500 flex items-center gap-1.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-slate-500 text-[10px]">2</span>
            Document Upload
          </span>
          <span className="text-slate-600">→</span>
          <span className="text-slate-500 flex items-center gap-1.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-slate-500 text-[10px]">3</span>
            Requirements AI
          </span>
          <span className="text-slate-600">→</span>
          <span className="text-slate-500 flex items-center gap-1.5">
            <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-800 text-slate-500 text-[10px]">4</span>
            Publish
          </span>
        </div>

        {/* Error message */}
        {error && (
          <div className="mt-6 flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
            <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
            <p>{error}</p>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="mt-6 space-y-6">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8 space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Tender Number */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Tender ID / Bid Number *
                </label>
                <div className="relative">
                  <input
                    type="text"
                    required
                    value={tenderNumber}
                    onChange={(e) => setTenderNumber(e.target.value)}
                    placeholder="e.g. GEM/2026/B/1024"
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 font-mono focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
                  />
                </div>
                <p className="mt-1 text-[11px] text-slate-500">Unique identifier referenced across all bid submissions</p>
              </div>

              {/* Procuring Organization */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Procuring Organization / Ministry *
                </label>
                <div className="relative">
                  <Building2 className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <input
                    type="text"
                    required
                    value={organization}
                    onChange={(e) => setOrganization(e.target.value)}
                    placeholder="e.g. Ministry of Health & Family Welfare"
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
                  />
                </div>
              </div>
            </div>

            {/* Tender Title */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Tender Title *
              </label>
              <input
                type="text"
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Procurement and Installation of 50 High-Resolution Magnetic Resonance Imaging Scanners"
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Category */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Procurement Category *
                </label>
                <div className="relative">
                  <Layers className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <select
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
                  >
                    {SAMPLE_CATEGORIES.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Submission Deadline */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                  Submission Deadline (UTC) *
                </label>
                <div className="relative">
                  <Calendar className="absolute left-3.5 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-500" />
                  <input
                    type="datetime-local"
                    required
                    value={submissionDeadline}
                    onChange={(e) => setSubmissionDeadline(e.target.value)}
                    className="w-full rounded-xl border border-slate-800 bg-slate-950 pl-10 pr-4 py-2.5 text-sm text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
                  />
                </div>
                <p className="mt-1 text-[11px] text-amber-400/80">Bids submitted after this deadline will be rejected automatically</p>
              </div>
            </div>

            {/* Scope / Description */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
                Detailed Scope of Work & Description *
              </label>
              <textarea
                rows={4}
                required
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Specify detailed technical requirements, delivery locations, warranty terms, and mandatory certifications..."
                className="w-full rounded-xl border border-slate-800 bg-slate-950 px-4 py-2.5 text-sm text-slate-100 placeholder:text-slate-600 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-all"
              />
            </div>

            {/* Initial Status */}
            <div className="pt-4 border-t border-slate-800/80 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
              <div>
                <span className="text-xs font-semibold text-slate-200 uppercase tracking-wider block">
                  Initial Publication Status
                </span>
                <p className="text-xs text-slate-400">
                  Save as Draft to upload documents first, or publish immediately for public bidding.
                </p>
              </div>
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setInitialStatus("DRAFT")}
                  className={`rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                    initialStatus === "DRAFT"
                      ? "bg-amber-500/20 text-amber-300 border border-amber-500/30"
                      : "bg-slate-950 text-slate-400 border border-slate-800"
                  }`}
                >
                  Save as Draft
                </button>
                <button
                  type="button"
                  onClick={() => setInitialStatus("PUBLISHED")}
                  className={`rounded-xl px-4 py-2 text-xs font-semibold transition-all ${
                    initialStatus === "PUBLISHED"
                      ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30"
                      : "bg-slate-950 text-slate-400 border border-slate-800"
                  }`}
                >
                  Publish Now
                </button>
              </div>
            </div>
          </div>

          {/* Submit Action */}
          <div className="flex items-center justify-end gap-3">
            <Link
              href="/tenders"
              className="rounded-xl border border-slate-800 bg-slate-900 px-5 py-2.5 text-sm font-medium text-slate-300 hover:bg-slate-800 transition-colors"
            >
              Cancel
            </Link>
            <button
              type="submit"
              disabled={loading}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-6 py-2.5 text-sm font-semibold text-white shadow-lg shadow-emerald-600/25 hover:from-emerald-500 hover:to-teal-400 transition-all disabled:opacity-50"
            >
              {loading ? (
                <span>Creating Tender...</span>
              ) : (
                <>
                  <CheckCircle className="h-4 w-4" />
                  Create Tender
                </>
              )}
            </button>
          </div>
        </form>
      </main>
    </div>
  );
}
