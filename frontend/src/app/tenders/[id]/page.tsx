"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import {
  FileText,
  ArrowLeft,
  Building2,
  Calendar,
  Layers,
  Clock,
  CheckCircle2,
  Lock,
  RefreshCw,
  AlertCircle,
  UploadCloud,
  FileCheck,
  Send,
  XCircle,
  Download,
  Trash2,
  FileCode,
  ShieldCheck,
  PlusCircle,
} from "lucide-react";
import {
  fetchTenderById,
  TenderItem,
  updateTenderStatusApi,
  fetchTenderDocumentsApi,
  uploadTenderDocumentApi,
  downloadTenderDocumentApi,
  deleteTenderDocumentApi,
  TenderDocumentItem,
  fetchCurrentUserApi,
} from "@/lib/api";

export default function TenderDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const tenderId = resolvedParams.id;

  const [tender, setTender] = useState<TenderItem | null>(null);
  const [documents, setDocuments] = useState<TenderDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [statusUpdating, setStatusUpdating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    setToken(sessionToken);
    loadTender(sessionToken);
    loadDocuments(sessionToken);
    if (sessionToken) {
      fetchCurrentUserApi(sessionToken)
        .then((user) => setRole(user.roles[0] || ""))
        .catch(() => setRole(""));
    }
  }, [tenderId]);

  async function loadTender(authToken: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTenderById(tenderId, authToken || token);
      setTender(data);
    } catch (err: any) {
      setError(err.message || "Failed to load tender details");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments(authToken: string) {
    setDocsLoading(true);
    setDocError(null);
    try {
      const res = await fetchTenderDocumentsApi(tenderId, authToken || token);
      setDocuments(res.items || []);
    } catch (err: any) {
      setDocError(err.message || "Failed to load attached documents");
    } finally {
      setDocsLoading(false);
    }
  }

  async function handleStatusChange(newStatus: string) {
    setStatusUpdating(true);
    try {
      const updated = await updateTenderStatusApi(tenderId, newStatus, token);
      setTender(updated);
    } catch (err: any) {
      alert(`Status update failed: ${err.message}`);
    } finally {
      setStatusUpdating(false);
    }
  }

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setDocError(null);
    try {
      await uploadTenderDocumentApi(tenderId, file, token);
      await loadDocuments(token);
      await loadTender(token);
    } catch (err: any) {
      setDocError(err.message || "Upload failed");
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  async function handleDownload(docId: string, filename: string) {
    try {
      await downloadTenderDocumentApi(tenderId, docId, filename, token);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  }

  async function handleDeleteDocument(docId: string, filename: string) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      await deleteTenderDocumentApi(tenderId, docId, token);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      await loadTender(token);
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  function formatBytes(bytes: number) {
    if (bytes === 0) return "0 Bytes";
    const k = 1024;
    const sizes = ["Bytes", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "PUBLISHED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Published
          </span>
        );
      case "DRAFT":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-400 border border-amber-500/20">
            <Clock className="h-3.5 w-3.5" /> Draft
          </span>
        );
      case "CLOSED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-500/10 px-3 py-1 text-xs font-semibold text-slate-400 border border-slate-500/20">
            <Lock className="h-3.5 w-3.5" /> Closed
          </span>
        );
      case "UNDER_EVALUATION":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500/20">
            <RefreshCw className="h-3.5 w-3.5" /> Under Evaluation
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-slate-400 border border-slate-700">
            {status}
          </span>
        );
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navigation />
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3 text-emerald-400">
            <RefreshCw className="h-6 w-6 animate-spin" />
            <span className="text-sm font-medium">Loading tender data...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !tender) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navigation />
        <main className="flex-1 mx-auto w-full max-w-4xl px-4 py-12 sm:px-6">
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-8 text-center space-y-4">
            <AlertCircle className="h-10 w-10 text-rose-400 mx-auto" />
            <h2 className="text-xl font-bold text-white">Error Loading Tender</h2>
            <p className="text-sm text-rose-300">{error || "Tender record not found."}</p>
            <Link
              href="/tenders"
              className="inline-flex items-center gap-2 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
            >
              <ArrowLeft className="h-4 w-4" /> Return to Catalog
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const deadlineDate = new Date(tender.submission_deadline);
  const isPast = deadlineDate < new Date();
  const canManageTender = role === "ADMIN" || role === "PROCUREMENT_OFFICER";
  const canUploadDocs = canManageTender && (tender.status === "DRAFT" || tender.status === "PUBLISHED");
  const canDeleteDocs = canManageTender && tender.status === "DRAFT";
  const canBid = role === "BIDDER" && tender.status === "PUBLISHED" && !isPast;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Back Link */}
        <Link
          href="/tenders"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to Tender Catalog
        </Link>

        {/* Main Header Banner */}
        <div className="rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/90 to-slate-900/40 p-6 sm:p-8 space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-mono text-xs font-bold text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-lg border border-emerald-500/20">
                  {tender.tender_number}
                </span>
                {getStatusBadge(tender.status)}
                {tender.category && (
                  <span className="text-xs text-slate-400 bg-slate-800/80 px-2.5 py-1 rounded-md border border-slate-700">
                    {tender.category}
                  </span>
                )}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">{tender.title}</h1>
              <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                <span className="flex items-center gap-1.5">
                  <Building2 className="h-4 w-4 text-slate-500" />
                  {tender.organization}
                </span>
                <span>•</span>
                <span>Created: {new Date(tender.created_at).toLocaleDateString()}</span>
                {tender.created_by_name && (
                  <>
                    <span>•</span>
                    <span>Officer: {tender.created_by_name}</span>
                  </>
                )}
              </div>
            </div>

            {/* Lifecycle Controls */}
            {canManageTender && <div className="flex items-center gap-2 flex-wrap">
              {tender.status === "DRAFT" && (
                <button
                  onClick={() => handleStatusChange("PUBLISHED")}
                  disabled={statusUpdating}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/25 hover:from-emerald-500 hover:to-teal-400 transition-all active:scale-95 disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" /> Publish Tender
                </button>
              )}
              {tender.status === "PUBLISHED" && (
                <button
                  onClick={() => handleStatusChange("CLOSED")}
                  disabled={statusUpdating}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-800 border border-slate-700 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-all disabled:opacity-50"
                >
                  <Lock className="h-3.5 w-3.5 text-amber-400" /> Close Submissions
                </button>
              )}
              {tender.status !== "CANCELLED" && tender.status !== "COMPLETED" && (
                <button
                  onClick={() => handleStatusChange("CANCELLED")}
                  disabled={statusUpdating}
                  className="inline-flex items-center gap-2 rounded-xl bg-rose-500/10 border border-rose-500/20 px-3 py-2 text-xs font-medium text-rose-400 hover:bg-rose-500/20 transition-all disabled:opacity-50"
                >
                  <XCircle className="h-3.5 w-3.5" /> Cancel
                </button>
              )}
            </div>}
          </div>

          {/* Quick Metrics Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 border-t border-slate-800/80">
            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Submission Deadline
              </span>
              <p className={`mt-1 text-sm font-semibold ${isPast ? "text-rose-400" : "text-amber-400"}`}>
                {deadlineDate.toLocaleString()}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Tender Documents
              </span>
              <p className="mt-1 text-sm font-semibold text-slate-200">
                {documents.length} Files Attached
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Extracted Rules
              </span>
              <p className="mt-1 text-sm font-semibold text-emerald-400">
                {tender.requirements_count} Requirements
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Bids Received
              </span>
              <p className="mt-1 text-sm font-semibold text-teal-400">
                {tender.bids_count} Submissions
              </p>
            </div>
          </div>
        </div>

        {canBid && (
          <section className="rounded-2xl border border-emerald-500/25 bg-emerald-500/5 p-6 sm:p-8 flex flex-col sm:flex-row sm:items-center justify-between gap-5">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2"><ShieldCheck className="h-5 w-5 text-emerald-400" /> Bidder Credentials & Assets</h2>
              <p className="mt-1 text-sm text-slate-400">Create your bid, then upload GST, PAN, company registration, financial, technical, and other credential documents for this tender.</p>
            </div>
            <Link href={`/bids/new?tender_id=${tender.id}`} className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2.5 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 hover:from-emerald-500 hover:to-teal-400">
              <UploadCloud className="h-4 w-4" /> Submit Bid & Upload Credentials
            </Link>
          </section>
        )}

        {/* Tender Specification Documents Section */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <FileCode className="h-5 w-5 text-emerald-400" />
                Tender Specifications & RFP Documents
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                Official procurement guidelines, technical requirements, and RFP documents.
              </p>
            </div>

            {/* Upload Button for Officers */}
            {canUploadDocs && (
              <label className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 hover:from-emerald-500 hover:to-teal-400 transition-all cursor-pointer">
                {uploading ? (
                  <RefreshCw className="h-4 w-4 animate-spin" />
                ) : (
                  <PlusCircle className="h-4 w-4" />
                )}
                <span>{uploading ? "Uploading Document..." : "Upload Specification PDF"}</span>
                <input
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
                  onChange={handleFileUpload}
                  disabled={uploading}
                  className="hidden"
                />
              </label>
            )}
          </div>

          {docError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{docError}</span>
            </div>
          )}

          {docsLoading ? (
            <div className="flex items-center justify-center py-10 text-emerald-400 gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              <span className="text-xs font-medium">Fetching documents...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center space-y-2">
              <UploadCloud className="h-8 w-8 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No Tender Documents Attached</p>
              <p className="text-xs text-slate-500">
                {canUploadDocs
                  ? "Upload official RFP specifications to allow bidders to review requirements."
                  : "No official documents currently available."}
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="rounded-xl border border-slate-800 bg-slate-950/60 p-4 hover:border-slate-700 transition-all space-y-3"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-emerald-500/10 p-2.5 text-emerald-400 border border-emerald-500/20">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <h4 className="text-sm font-semibold text-white truncate max-w-[220px] sm:max-w-xs" title={doc.filename}>
                          {doc.filename}
                        </h4>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          <span>{formatBytes(doc.file_size)}</span>
                          <span>•</span>
                          <span className="font-mono text-[10px] text-slate-500 truncate max-w-[100px]" title={doc.file_hash}>
                            SHA: {doc.file_hash.substring(0, 10)}...
                          </span>
                        </div>
                      </div>
                    </div>

                    <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                      {doc.status}
                    </span>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                    <span className="text-[11px] text-slate-500">
                      Uploaded {new Date(doc.created_at).toLocaleDateString()}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleDownload(doc.id, doc.filename)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-slate-800 px-3 py-1.5 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-all"
                      >
                        <Download className="h-3.5 w-3.5 text-emerald-400" /> Download
                      </button>

                      {canDeleteDocs && (
                        <button
                          onClick={() => handleDeleteDocument(doc.id, doc.filename)}
                          className="rounded-lg bg-rose-500/10 p-1.5 text-rose-400 hover:bg-rose-500/20 transition-all border border-rose-500/20"
                          title="Delete Document"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Detailed Scope */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FileText className="h-5 w-5 text-emerald-400" />
            Tender Scope & Specifications
          </h2>
          <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {tender.description || "No specific detailed description provided for this tender."}
          </div>
        </div>
      </main>
    </div>
  );
}
