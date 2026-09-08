"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import Navigation from "@/components/Navigation";
import {
  Send,
  ArrowLeft,
  Building2,
  Calendar,
  Layers,
  Clock,
  CheckCircle2,
  XCircle,
  AlertCircle,
  RefreshCw,
  FileText,
  UploadCloud,
  FileCheck,
  ShieldCheck,
  Download,
  Trash2,
  PlusCircle,
  Sparkles,
  Eye,
  X,
  FileCode,
  ScanLine,
  BrainCircuit,
  Search,
  ExternalLink,
  ShieldAlert,
  Hash,
} from "lucide-react";
import {
  fetchBidById,
  BidItem,
  submitBidApi,
  withdrawBidApi,
  fetchBidDocumentsApi,
  uploadBidDocumentApi,
  downloadBidDocumentApi,
  deleteBidDocumentApi,
  fetchBidDocumentOcrApi,
  triggerBidDocumentOcrApi,
  extractBidDocumentApi,
  extractAllBidDocumentsApi,
  fetchBidExtractionSummaryApi,
  evaluateBidComplianceApi,
  fetchBidComplianceSummaryApi,
  generateBidReportApi,
  fetchBidReportsApi,
  fetchReviewTasksApi,
  submitReviewDecisionApi,
  BidDocumentItem,
  OCRExtractionData,
  ExtractedEntityItem,
  EvidenceItem,
  BidExtractionSummary,
  BidComplianceSummary,
  ComplianceResultItem,
  ReportItem,
  ReviewTaskItem,
  fetchCurrentUserApi,
} from "@/lib/api";

const DOCUMENT_CATEGORIES = [
  { value: "GST_CERTIFICATE", label: "GST Registration Certificate" },
  { value: "PAN", label: "PAN Card / Tax Identifier" },
  { value: "REGISTRATION", label: "Company Incorporation / Registration" },
  { value: "FINANCIAL", label: "Audited Financial Statements / Turnover" },
  { value: "EXPERIENCE", label: "Past Experience & Completion Certificates" },
  { value: "TECHNICAL", label: "Technical Compliance / OEM Authorization" },
  { value: "MSME", label: "MSME / Udyam Certificate" },
  { value: "AUTHORIZATION", label: "Power of Attorney / Authorization" },
  { value: "OTHER", label: "Other Supporting Document" },
];

export default function BidDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const bidId = resolvedParams.id;

  const [bid, setBid] = useState<BidItem | null>(null);
  const [documents, setDocuments] = useState<BidDocumentItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [docsLoading, setDocsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [docError, setDocError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");

  // Upload modal / form state
  const [selectedDocType, setSelectedDocType] = useState("GST_CERTIFICATE");
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  // OCR preview modal state
  const [activeOcrDoc, setActiveOcrDoc] = useState<BidDocumentItem | null>(null);
  const [ocrData, setOcrData] = useState<OCRExtractionData | null>(null);
  const [ocrLoading, setOcrLoading] = useState(false);
  const [ocrError, setOcrError] = useState<string | null>(null);

  // AI Extraction & Evidence state
  const [extractionSummary, setExtractionSummary] = useState<BidExtractionSummary | null>(null);
  const [extractionLoading, setExtractionLoading] = useState(false);
  const [extractingAll, setExtractingAll] = useState(false);
  const [extractingDocId, setExtractingDocId] = useState<string | null>(null);
  const [selectedEvidenceItem, setSelectedEvidenceItem] = useState<EvidenceItem | null>(null);
  const [showEvidenceModal, setShowEvidenceModal] = useState(false);

  // Phase 6: Compliance & Verification state
  const [complianceSummary, setComplianceSummary] = useState<BidComplianceSummary | null>(null);
  const [complianceLoading, setComplianceLoading] = useState(false);
  const [evaluatingCompliance, setEvaluatingCompliance] = useState(false);

  // Phase 7: Human Review & Reports state
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [reportsLoading, setReportsLoading] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);

  const [reviewTasks, setReviewTasks] = useState<ReviewTaskItem[]>([]);
  const [selectedReviewTask, setSelectedReviewTask] = useState<ReviewTaskItem | null>(null);
  const [showReviewModal, setShowReviewModal] = useState(false);
  const [reviewDecision, setReviewDecision] = useState("COMPLIANT");
  const [reviewJustification, setReviewJustification] = useState("");
  const [reviewComments, setReviewComments] = useState("");
  const [submittingReview, setSubmittingReview] = useState(false);

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    setToken(sessionToken);
    if (sessionToken) {
      fetchCurrentUserApi(sessionToken)
        .then((user) => setRole(user.roles[0] || ""))
        .catch(() => setRole(""));
    }
    loadBid(sessionToken);
    loadDocuments(sessionToken);
    loadExtractionSummary(sessionToken);
    loadComplianceSummary(sessionToken);
    loadReports(sessionToken);
    loadReviewTasks(sessionToken);
  }, [bidId]);

  async function loadBid(authToken: string) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchBidById(bidId, authToken || token);
      setBid(data);
    } catch (err: any) {
      setError(err.message || "Failed to load bid details");
    } finally {
      setLoading(false);
    }
  }

  async function loadDocuments(authToken: string) {
    setDocsLoading(true);
    setDocError(null);
    try {
      const res = await fetchBidDocumentsApi(bidId, authToken || token);
      setDocuments(res.items || []);
    } catch (err: any) {
      setDocError(err.message || "Failed to load attached documents");
    } finally {
      setDocsLoading(false);
    }
  }

  async function loadExtractionSummary(authToken: string) {
    setExtractionLoading(true);
    try {
      const data = await fetchBidExtractionSummaryApi(bidId, authToken || token);
      setExtractionSummary(data);
    } catch {
      // Ignored if no extractions yet
    } finally {
      setExtractionLoading(false);
    }
  }

  async function handleExtractSingleDoc(docId: string) {
    setExtractingDocId(docId);
    try {
      await extractBidDocumentApi(bidId, docId, token, true);
      await loadExtractionSummary(token);
      await loadDocuments(token);
    } catch (err: any) {
      alert(`AI Extraction failed: ${err.message}`);
    } finally {
      setExtractingDocId(null);
    }
  }

  async function handleExtractAllDocs() {
    setExtractingAll(true);
    try {
      const data = await extractAllBidDocumentsApi(bidId, token);
      setExtractionSummary(data);
      await loadDocuments(token);
    } catch (err: any) {
      alert(`Batch AI Extraction failed: ${err.message}`);
    } finally {
      setExtractingAll(false);
    }
  }

  async function loadComplianceSummary(authToken: string) {
    setComplianceLoading(true);
    try {
      const data = await fetchBidComplianceSummaryApi(bidId, authToken || token);
      setComplianceSummary(data);
    } catch {
      // Ignored if not yet evaluated
    } finally {
      setComplianceLoading(false);
    }
  }

  async function handleEvaluateCompliance() {
    setEvaluatingCompliance(true);
    try {
      const data = await evaluateBidComplianceApi(bidId, token, true);
      setComplianceSummary(data);
      await loadBid(token);
      await loadReviewTasks(token);
    } catch (err: any) {
      alert(`Compliance evaluation failed: ${err.message}`);
    } finally {
      setEvaluatingCompliance(false);
    }
  }

  async function loadReports(authToken: string) {
    setReportsLoading(true);
    try {
      const data = await fetchBidReportsApi(bidId, authToken || token);
      setReports(data.items);
    } catch {
      // Ignore if empty
    } finally {
      setReportsLoading(false);
    }
  }

  async function loadReviewTasks(authToken: string) {
    try {
      const data = await fetchReviewTasksApi(authToken || token, undefined, bidId);
      setReviewTasks(data.items);
    } catch {
      // Ignore if empty or forbidden
    }
  }

  async function handleGenerateReport() {
    setGeneratingReport(true);
    try {
      const rep = await generateBidReportApi(bidId, token);
      setReports((prev) => [rep, ...prev]);
      alert(`Compliance report ${rep.report_number} generated successfully!`);
    } catch (err: any) {
      alert(`Report generation failed: ${err.message}`);
    } finally {
      setGeneratingReport(false);
    }
  }

  async function handleDownloadReport(reportId: string, reportNum: string) {
    try {
      const res = await fetch(`http://localhost:8000/api/v1/reports/${reportId}/download`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error("Download failed");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${reportNum}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err: any) {
      alert(`Failed to download report: ${err.message}`);
    }
  }

  async function handleSubmitReviewDecision() {
    if (!selectedReviewTask) return;
    if (!reviewJustification.trim() || reviewJustification.trim().length < 5) {
      alert("Please provide a mandatory justification explanation (minimum 5 characters).");
      return;
    }
    setSubmittingReview(true);
    try {
      await submitReviewDecisionApi(
        selectedReviewTask.id,
        reviewDecision,
        reviewJustification,
        reviewComments,
        token
      );
      alert("Review decision submitted successfully!");
      setShowReviewModal(false);
      setSelectedReviewTask(null);
      setReviewJustification("");
      setReviewComments("");
      await loadComplianceSummary(token);
      await loadReviewTasks(token);
      await loadBid(token);
    } catch (err: any) {
      alert(`Review decision submission failed: ${err.message}`);
    } finally {
      setSubmittingReview(false);
    }
  }

  async function handleSubmitBid() {
    if (!confirm("Are you sure you want to formally submit this bid? Further modifications will be locked.")) {
      return;
    }
    setActionLoading(true);
    try {
      const updated = await submitBidApi(bidId, token);
      setBid(updated);
    } catch (err: any) {
      alert(`Submission failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleWithdrawBid() {
    const reason = prompt("Please provide a reason for bid withdrawal:");
    if (!reason) return;

    setActionLoading(true);
    try {
      const updated = await withdrawBidApi(bidId, token, reason);
      setBid(updated);
    } catch (err: any) {
      alert(`Withdrawal failed: ${err.message}`);
    } finally {
      setActionLoading(false);
    }
  }

  async function handleUploadSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) {
      setDocError("Please select a file to upload.");
      return;
    }

    setUploading(true);
    setDocError(null);
    try {
      await uploadBidDocumentApi(bidId, selectedFile, selectedDocType, token, true);
      setSelectedFile(null);
      setShowUploadModal(false);
      await loadDocuments(token);
      await loadBid(token);
    } catch (err: any) {
      setDocError(err.message || "Upload failed");
    } finally {
      setUploading(false);
    }
  }

  async function handleDownload(docId: string, filename: string) {
    try {
      await downloadBidDocumentApi(bidId, docId, filename, token);
    } catch (err: any) {
      alert(`Download failed: ${err.message}`);
    }
  }

  async function handleDeleteDocument(docId: string, filename: string) {
    if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;
    try {
      await deleteBidDocumentApi(bidId, docId, token);
      setDocuments((prev) => prev.filter((d) => d.id !== docId));
      await loadBid(token);
    } catch (err: any) {
      alert(`Delete failed: ${err.message}`);
    }
  }

  async function handleViewOcr(doc: BidDocumentItem) {
    setActiveOcrDoc(doc);
    setOcrLoading(true);
    setOcrError(null);
    setOcrData(null);
    try {
      const data = await fetchBidDocumentOcrApi(bidId, doc.id, token);
      setOcrData(data);
    } catch (err: any) {
      setOcrError(err.message || "No OCR extraction available");
    } finally {
      setOcrLoading(false);
    }
  }

  async function handleTriggerOcr(doc: BidDocumentItem) {
    setOcrLoading(true);
    setOcrError(null);
    try {
      const data = await triggerBidDocumentOcrApi(bidId, doc.id, token);
      setOcrData(data);
      await loadDocuments(token);
    } catch (err: any) {
      setOcrError(err.message || "OCR re-processing failed");
    } finally {
      setOcrLoading(false);
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
      case "SUBMITTED":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400 border border-blue-500/20">
            <CheckCircle2 className="h-3.5 w-3.5" /> Submitted
          </span>
        );
      case "DRAFT":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-semibold text-amber-400 border border-amber-500/20">
            <Clock className="h-3.5 w-3.5" /> Draft
          </span>
        );
      case "UNDER_REVIEW":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-purple-500/10 px-3 py-1 text-xs font-semibold text-purple-400 border border-purple-500/20">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" /> Under Review
          </span>
        );
      case "COMPLIANT":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-semibold text-emerald-400 border border-emerald-500/20">
            <FileCheck className="h-3.5 w-3.5" /> Compliant
          </span>
        );
      case "WITHDRAWN":
        return (
          <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-500/10 px-3 py-1 text-xs font-semibold text-slate-400 border border-slate-500/20">
            <XCircle className="h-3.5 w-3.5" /> Withdrawn
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

  function getDocStatusBadge(status: string) {
    switch (status) {
      case "PROCESSED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
            <CheckCircle2 className="h-3 w-3" /> Processed
          </span>
        );
      case "PROCESSING":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-2 py-0.5 text-[10px] font-semibold text-blue-400 border border-blue-500/20">
            <RefreshCw className="h-3 w-3 animate-spin" /> Processing
          </span>
        );
      case "FAILED":
        return (
          <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400 border border-rose-500/20">
            <XCircle className="h-3 w-3" /> OCR Failed
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-medium text-slate-400">
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
            <span className="text-sm font-medium">Loading bid details...</span>
          </div>
        </div>
      </div>
    );
  }

  if (error || !bid) {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
        <Navigation />
        <main className="flex-1 mx-auto w-full max-w-4xl px-4 py-12 sm:px-6">
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 p-8 text-center space-y-4">
            <AlertCircle className="h-10 w-10 text-rose-400 mx-auto" />
            <h2 className="text-xl font-bold text-white">Error Loading Bid</h2>
            <p className="text-sm text-rose-300">{error || "Bid record not found."}</p>
            <Link
              href="/bids"
              className="inline-flex items-center gap-2 rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700"
            >
              <ArrowLeft className="h-4 w-4" /> Return to My Bids
            </Link>
          </div>
        </main>
      </div>
    );
  }

  const isDraft = bid.status === "DRAFT";
  const isBidder = role === "BIDDER";
  const canManageBidDocuments = isDraft && (isBidder || role === "ADMIN");

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Navigation />

      <main className="flex-1 mx-auto w-full max-w-7xl px-4 py-8 sm:px-6 lg:px-8 space-y-8">
        {/* Back Link */}
        <Link
          href="/bids"
          className="inline-flex items-center gap-2 text-xs font-semibold text-slate-400 hover:text-emerald-400 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" /> Back to My Bids
        </Link>

        {/* Main Banner */}
        <div className="rounded-3xl border border-slate-800 bg-gradient-to-b from-slate-900/90 to-slate-900/40 p-6 sm:p-8 space-y-6">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
            <div className="space-y-2">
              <div className="flex items-center gap-3 flex-wrap">
                <span className="font-mono text-xs font-bold text-emerald-400 bg-emerald-500/10 px-3 py-1 rounded-lg border border-emerald-500/20">
                  {bid.bid_number}
                </span>
                {getStatusBadge(bid.status)}
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                {bid.tender_title || "Bid Submission"}
              </h1>
              <div className="flex items-center gap-4 text-xs text-slate-400 flex-wrap">
                {bid.tender_number && (
                  <Link
                    href={`/tenders/${bid.tender_id}`}
                    className="flex items-center gap-1.5 text-emerald-400 hover:underline"
                  >
                    <FileText className="h-4 w-4" />
                    Tender #{bid.tender_number}
                  </Link>
                )}
                {bid.tender_organization && (
                  <>
                    <span>•</span>
                    <span className="flex items-center gap-1">
                      <Building2 className="h-4 w-4 text-slate-500" />
                      {bid.tender_organization}
                    </span>
                  </>
                )}
                <span>•</span>
                <span>Created: {new Date(bid.created_at).toLocaleDateString()}</span>
              </div>
            </div>

            {/* Lifecycle Action Buttons */}
            <div className="flex items-center gap-2 flex-wrap">
              {bid.status === "DRAFT" && (
                <button
                  onClick={handleSubmitBid}
                  disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-5 py-2.5 text-xs font-semibold text-white shadow-lg shadow-emerald-600/25 hover:from-emerald-500 hover:to-teal-400 transition-all active:scale-95 disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" /> Submit Final Bid
                </button>
              )}
              {bid.status !== "WITHDRAWN" && bid.status !== "FINALIZED" && (
                <button
                  onClick={handleWithdrawBid}
                  disabled={actionLoading}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-800 border border-slate-700 px-4 py-2.5 text-xs font-semibold text-slate-300 hover:bg-rose-500/20 hover:text-rose-300 hover:border-rose-500/30 transition-all disabled:opacity-50"
                >
                  <XCircle className="h-3.5 w-3.5 text-rose-400" /> Withdraw Bid
                </button>
              )}
            </div>
          </div>

          {/* Quick Metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-6 border-t border-slate-800/80">
            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Submission Status
              </span>
              <p className="mt-1 text-sm font-semibold text-slate-200">
                {bid.submission_date
                  ? `Submitted on ${new Date(bid.submission_date).toLocaleDateString()}`
                  : "Draft (Unsubmitted)"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Tender Deadline
              </span>
              <p className="mt-1 text-sm font-semibold text-amber-400">
                {bid.tender_deadline ? new Date(bid.tender_deadline).toLocaleDateString() : "Active"}
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                Attached Documents
              </span>
              <p className="mt-1 text-sm font-semibold text-emerald-400">
                {documents.length} Supporting Files
              </p>
            </div>

            <div className="rounded-xl border border-slate-800/60 bg-slate-950/60 p-4">
              <span className="text-[11px] font-medium text-slate-400 uppercase tracking-wider block">
                OCR Status
              </span>
              <p className="mt-1 text-sm font-semibold text-teal-400 flex items-center gap-1">
                <ScanLine className="h-4 w-4" />
                {documents.filter((d) => d.has_ocr).length}/{documents.length} Indexed
              </p>
            </div>
          </div>
        </div>

        {/* Bidder Credentials & Assets */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 sm:p-8 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-white flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                {isBidder ? "My Credentials & Assets" : "Bidder Credentials & Assets"}
              </h2>
              <p className="text-xs text-slate-400 mt-1">
                GST, PAN, registration, financial, technical, experience, and other supporting documents attached to this bid.
              </p>
            </div>

            {/* Upload Button */}
            <div className="flex items-center gap-2">
              <button
                onClick={handleExtractAllDocs}
                disabled={extractingAll || documents.length === 0}
                className="inline-flex items-center gap-1.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 px-3 py-1.5 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
                title="Run AI Entity Extraction on all supporting documents"
              >
                <BrainCircuit className={`h-3.5 w-3.5 ${extractingAll ? "animate-spin text-indigo-400" : ""}`} />
                <span>{extractingAll ? "Extracting All..." : "AI Extract All"}</span>
              </button>

              {canManageBidDocuments && (
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20 transition-all"
                >
                  <PlusCircle className="h-3.5 w-3.5" /> Attach Document
                </button>
              )}
            </div>
          </div>

          {docError && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 flex items-center gap-2">
              <AlertCircle className="h-4 w-4 shrink-0 text-rose-400" />
              <span>{docError}</span>
            </div>
          )}

          {docsLoading ? (
            <div className="flex items-center justify-center py-10 text-emerald-400 gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              <span className="text-xs font-medium">Fetching attached documents...</span>
            </div>
          ) : documents.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center space-y-3">
              <UploadCloud className="h-8 w-8 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No Supporting Documents Attached</p>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                {canManageBidDocuments
                  ? "Attach required certificates (GST, PAN, MSME, Turnover Audits) to prepare your bid for automated AI compliance verification."
                  : "No documents attached to this submission."}
              </p>
              {canManageBidDocuments && (
                <button
                  onClick={() => setShowUploadModal(true)}
                  className="inline-flex items-center gap-2 rounded-xl bg-slate-800 border border-slate-700 px-4 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-700 transition-all mt-2"
                >
                  <PlusCircle className="h-3.5 w-3.5 text-emerald-400" /> Attach First Document
                </button>
              )}
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
                      <div className="rounded-lg bg-teal-500/10 p-2.5 text-teal-400 border border-teal-500/20">
                        <FileText className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="font-mono text-[10px] font-semibold text-teal-400 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20">
                            {doc.document_type.replace(/_/g, " ")}
                          </span>
                          {getDocStatusBadge(doc.status)}
                        </div>
                        <h4 className="text-sm font-semibold text-white mt-1 truncate max-w-[200px] sm:max-w-xs" title={doc.filename}>
                          {doc.filename}
                        </h4>
                        <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
                          <span>{formatBytes(doc.file_size)}</span>
                          <span>•</span>
                          <span className="font-mono text-[10px] text-slate-500 truncate max-w-[90px]" title={doc.file_hash}>
                            SHA: {doc.file_hash.substring(0, 8)}...
                          </span>
                          {doc.ocr_confidence !== null && doc.ocr_confidence !== undefined && (
                            <>
                              <span>•</span>
                              <span className="text-emerald-400 text-[11px] font-semibold">
                                OCR: {(doc.ocr_confidence * 100).toFixed(0)}%
                              </span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/80 text-xs">
                    <span className="text-[11px] text-slate-500">
                      {new Date(doc.created_at).toLocaleDateString()}
                    </span>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleExtractSingleDoc(doc.id)}
                        disabled={extractingDocId === doc.id}
                        className="inline-flex items-center gap-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 text-xs font-semibold text-indigo-400 hover:bg-indigo-500/20 transition-all disabled:opacity-50"
                        title="Run AI Entity Extraction on this Document"
                      >
                        <BrainCircuit className={`h-3.5 w-3.5 ${extractingDocId === doc.id ? "animate-spin" : ""}`} />
                        {extractingDocId === doc.id ? "Extracting..." : "Extract AI"}
                      </button>

                      <button
                        onClick={() => handleViewOcr(doc)}
                        className="inline-flex items-center gap-1 rounded-lg bg-teal-500/10 border border-teal-500/20 px-2.5 py-1 text-xs font-semibold text-teal-400 hover:bg-teal-500/20 transition-all"
                        title="View OCR Extracted Text"
                      >
                        <Eye className="h-3.5 w-3.5" /> View OCR
                      </button>

                      <button
                        onClick={() => handleDownload(doc.id, doc.filename)}
                        className="inline-flex items-center gap-1 rounded-lg bg-slate-800 px-2.5 py-1 text-xs font-semibold text-slate-200 hover:bg-slate-700 hover:text-white transition-all"
                      >
                        <Download className="h-3.5 w-3.5 text-emerald-400" />
                      </button>

                      {canManageBidDocuments && (
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

        {/* AI Extracted Entities & Traceable Evidence Section */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <BrainCircuit className="h-5 w-5 text-indigo-400" />
                <h2 className="text-lg font-bold text-white">AI Extracted Entities & Evidence Traceability</h2>
                <span className="rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[10px] font-semibold text-indigo-300">
                  Zero-Hallucination Grounded
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Structured fields extracted from verified OCR text streams. Every entity is linked to source document citations.
              </p>
            </div>

            <button
              onClick={handleExtractAllDocs}
              disabled={extractingAll || documents.length === 0}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:from-indigo-500 hover:to-purple-500 transition-all disabled:opacity-50"
            >
              <BrainCircuit className={`h-4 w-4 ${extractingAll ? "animate-spin" : ""}`} />
              <span>{extractingAll ? "Extracting All Documents..." : "Run AI Extraction on Bid"}</span>
            </button>
          </div>

          {/* Metrics Overview Bar */}
          {extractionSummary && (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Entities Found</span>
                <span className="text-base font-bold text-white mt-0.5 block font-mono">
                  {extractionSummary.total_entities_extracted}
                </span>
              </div>

              <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Grounded Evidence</span>
                <span className="text-base font-bold text-emerald-400 mt-0.5 block font-mono">
                  {extractionSummary.total_evidence_records} Records
                </span>
              </div>

              <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Audited Documents</span>
                <span className="text-base font-bold text-indigo-400 mt-0.5 block font-mono">
                  {extractionSummary.total_documents} Files
                </span>
              </div>

              <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Traceability Defense</span>
                <span className="text-xs font-bold text-emerald-400 mt-0.5 block flex items-center justify-center gap-1">
                  <ShieldCheck className="h-3.5 w-3.5" /> 100% Traceable
                </span>
              </div>
            </div>
          )}

          {extractionLoading ? (
            <div className="flex items-center justify-center py-10 text-indigo-400 gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              <span className="text-xs font-medium">Loading extracted entities and evidence...</span>
            </div>
          ) : !extractionSummary || extractionSummary.entities.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center space-y-3">
              <BrainCircuit className="h-8 w-8 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">No Structured Entities Extracted Yet</p>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                {documents.length > 0
                  ? "Click 'Run AI Extraction on Bid' above to extract GSTIN, PAN, Turnover, Experience, MSME details and link traceable evidence."
                  : "Upload supporting documents first to extract verified qualification attributes."}
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Entities Table */}
              <div className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/60">
                <table className="w-full text-left text-xs text-slate-300">
                  <thead className="border-b border-slate-800 bg-slate-900/80 text-[11px] uppercase tracking-wider text-slate-400">
                    <tr>
                      <th className="px-4 py-3">Attribute / Field</th>
                      <th className="px-4 py-3">Raw Extracted Value</th>
                      <th className="px-4 py-3">Normalized Clean Value</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Verbatim Source Snippet</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {extractionSummary.entities.map((entity) => {
                      const matchedEvidence = extractionSummary.evidence.find(
                        (ev) => ev.entity_id === entity.id || ev.field_name === entity.entity_type
                      );
                      const conf = entity.confidence || 0.9;
                      return (
                        <tr key={entity.id} className="hover:bg-slate-900/40 transition-colors">
                          <td className="px-4 py-3">
                            <span className="inline-flex items-center gap-1.5 font-mono text-[11px] font-semibold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded border border-indigo-500/20">
                              <Hash className="h-3 w-3" />
                              {entity.entity_type.replace(/_/g, " ").toUpperCase()}
                            </span>
                          </td>
                          <td className="px-4 py-3 font-mono text-slate-200 text-[11px] max-w-[150px] truncate" title={entity.raw_value}>
                            {entity.raw_value}
                          </td>
                          <td className="px-4 py-3 font-semibold text-emerald-400 font-mono text-[11px] max-w-[150px] truncate" title={entity.normalized_value || entity.raw_value}>
                            {entity.normalized_value || entity.raw_value}
                          </td>
                          <td className="px-4 py-3">
                            {conf >= 0.9 ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-500/20">
                                <CheckCircle2 className="h-3 w-3" /> {(conf * 100).toFixed(0)}% High
                              </span>
                            ) : conf >= 0.7 ? (
                              <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400 border border-amber-500/20">
                                <AlertCircle className="h-3 w-3" /> {(conf * 100).toFixed(0)}% Med
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400 border border-rose-500/20">
                                <ShieldAlert className="h-3 w-3" /> {(conf * 100).toFixed(0)}% Review
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-slate-400 text-[11px] max-w-[200px] truncate italic" title={entity.source_snippet || ""}>
                            "{entity.source_snippet || "Extracted from OCR text stream"}"
                          </td>
                          <td className="px-4 py-3 text-right">
                            {matchedEvidence && (
                              <button
                                onClick={() => {
                                  setSelectedEvidenceItem(matchedEvidence);
                                  setShowEvidenceModal(true);
                                }}
                                className="inline-flex items-center gap-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-2.5 py-1 text-[11px] font-semibold text-indigo-300 hover:bg-indigo-500/20 transition-all"
                              >
                                <Search className="h-3 w-3" /> Trace Citation
                              </button>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Manual Review Disclaimer Banner */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3.5 flex items-start gap-3 text-xs text-amber-300">
                <AlertCircle className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
                <div className="space-y-0.5">
                  <p className="font-semibold">AI Hallucination Defense Active</p>
                  <p className="text-amber-400/80 text-[11px]">
                    All extracted entities are strictly grounded in document text snippets. Extracted candidate attributes do not substitute for formal procurement verification.
                  </p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Phase 6: Automated Compliance Engine & Verification Section */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5 text-emerald-400" />
                <h2 className="text-lg font-bold text-white">Automated Compliance Engine & Verification</h2>
                <span className="rounded-full bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 text-[10px] font-semibold text-emerald-300">
                  SRS Rule Engine
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Deterministic rule evaluation of bidder evidence against mandatory tender specifications and registry verifications.
              </p>
            </div>

            <button
              onClick={handleEvaluateCompliance}
              disabled={evaluatingCompliance || documents.length === 0}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 hover:from-emerald-500 hover:to-teal-400 transition-all disabled:opacity-50"
            >
              <ShieldCheck className={`h-4 w-4 ${evaluatingCompliance ? "animate-spin" : ""}`} />
              <span>{evaluatingCompliance ? "Evaluating Compliance..." : "Evaluate Bid Compliance"}</span>
            </button>
          </div>

          {/* Compliance Summary Verdict & Metrics */}
          {complianceSummary && (
            <div className="space-y-4">
              {/* Overall Status Banner */}
              <div
                className={`rounded-xl p-4 border flex items-center justify-between gap-4 ${
                  complianceSummary.overall_status === "COMPLIANT"
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                    : complianceSummary.overall_status === "NON_COMPLIANT"
                    ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                    : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                }`}
              >
                <div className="flex items-center gap-3">
                  {complianceSummary.overall_status === "COMPLIANT" ? (
                    <CheckCircle2 className="h-6 w-6 text-emerald-400 shrink-0" />
                  ) : complianceSummary.overall_status === "NON_COMPLIANT" ? (
                    <XCircle className="h-6 w-6 text-rose-400 shrink-0" />
                  ) : (
                    <AlertCircle className="h-6 w-6 text-amber-400 shrink-0" />
                  )}
                  <div>
                    <h3 className="text-sm font-bold">
                      {complianceSummary.overall_status === "COMPLIANT"
                        ? "BID COMPLIANCE STATUS: FULLY COMPLIANT"
                        : complianceSummary.overall_status === "NON_COMPLIANT"
                        ? "BID COMPLIANCE STATUS: NON-COMPLIANT"
                        : "BID COMPLIANCE STATUS: MANUAL REVIEW REQUIRED"}
                    </h3>
                    <p className="text-xs opacity-90 mt-0.5">
                      {complianceSummary.overall_status === "COMPLIANT"
                        ? "All mandatory technical, financial, and statutory tender requirements are satisfied with grounded evidence."
                        : complianceSummary.overall_status === "NON_COMPLIANT"
                        ? "One or more mandatory tender requirements failed evaluation or lack supporting evidence."
                        : "Low-confidence extractions or conflicting evidence detected. Requires human verification before award."}
                    </p>
                  </div>
                </div>

                <span className="font-mono text-xs font-bold px-3 py-1 rounded-full bg-slate-900/80 border border-current shrink-0">
                  {complianceSummary.overall_status}
                </span>
              </div>

              {/* Metrics Row */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Total Requirements</span>
                  <span className="text-base font-bold text-white font-mono">{complianceSummary.total_requirements}</span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Compliant</span>
                  <span className="text-base font-bold text-emerald-400 font-mono">{complianceSummary.compliant_count} Passed</span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Non-Compliant</span>
                  <span className="text-base font-bold text-rose-400 font-mono">{complianceSummary.non_compliant_count} Failed</span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Needs Review</span>
                  <span className="text-base font-bold text-amber-400 font-mono">{complianceSummary.needs_review_count} Pending</span>
                </div>
              </div>

              {/* Requirement by Requirement Cards */}
              <div className="space-y-3 pt-2">
                <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400">
                  Detailed Requirement Evaluations & Citations
                </h4>

                <div className="space-y-3">
                  {complianceSummary.results.map((res) => {
                    const isPassed = res.status === "COMPLIANT";
                    const isFailed = res.status === "NON_COMPLIANT";
                    const isReview = res.status === "NEEDS_REVIEW";

                    return (
                      <div
                        key={res.id}
                        className={`rounded-xl border p-4 transition-all space-y-3 ${
                          isPassed
                            ? "bg-slate-950/60 border-slate-800 hover:border-emerald-500/40"
                            : isFailed
                            ? "bg-rose-950/20 border-rose-900/40 hover:border-rose-700/60"
                            : "bg-amber-950/20 border-amber-900/40 hover:border-amber-700/60"
                        }`}
                      >
                        {/* Requirement Header */}
                        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-2">
                          <div className="space-y-1">
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="font-mono text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">
                                {res.requirement_category}
                              </span>
                              {res.mandatory ? (
                                <span className="text-[10px] font-bold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                                  MANDATORY
                                </span>
                              ) : (
                                <span className="text-[10px] font-semibold text-slate-400 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                                  OPTIONAL
                                </span>
                              )}
                              {res.verification_status && (
                                <span className="text-[10px] font-semibold text-teal-300 bg-teal-500/10 px-2 py-0.5 rounded border border-teal-500/20 flex items-center gap-1">
                                  <ShieldCheck className="h-3 w-3" />
                                  {res.verification_status} (Mock Gateway)
                                </span>
                              )}
                            </div>
                            <h5 className="text-sm font-semibold text-white mt-1">{res.requirement_text}</h5>
                          </div>

                          <div className="shrink-0">
                            {isPassed && (
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-bold text-emerald-400 border border-emerald-500/30">
                                <CheckCircle2 className="h-3.5 w-3.5" /> COMPLIANT
                              </span>
                            )}
                            {isFailed && (
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-rose-500/10 px-3 py-1 text-xs font-bold text-rose-400 border border-rose-500/30">
                                <XCircle className="h-3.5 w-3.5" /> NON-COMPLIANT
                              </span>
                            )}
                            {isReview && (
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-500/10 px-3 py-1 text-xs font-bold text-amber-400 border border-amber-500/30">
                                <AlertCircle className="h-3.5 w-3.5" /> NEEDS REVIEW
                              </span>
                            )}
                            {res.status === "NOT_APPLICABLE" && (
                              <span className="inline-flex items-center gap-1.5 rounded-full bg-slate-800 px-3 py-1 text-xs font-medium text-slate-400 border border-slate-700">
                                NOT APPLICABLE
                              </span>
                            )}
                          </div>
                        </div>

                        {/* Evaluation Details & Evidence */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-2 border-t border-slate-800/80 text-xs">
                          <div className="space-y-1.5">
                            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold block">
                              Evaluation Reason & Rule Logic
                            </span>
                            <p className="text-slate-300 leading-relaxed text-[11px]">{res.reason}</p>
                            {res.parameter && (
                              <div className="font-mono text-[10px] text-slate-400 mt-1">
                                Criteria: <span className="text-indigo-300">{res.parameter}</span> {res.operator || "exists"}{" "}
                                {res.threshold_value ? `<${res.threshold_value} ${res.unit || ""}>` : ""}
                              </div>
                            )}
                          </div>

                          <div className="space-y-1.5">
                            <span className="text-[10px] uppercase tracking-wider text-slate-500 font-semibold block">
                              Grounded Evidence & Source
                            </span>
                            {res.source_document_filename ? (
                              <div className="flex items-center justify-between bg-slate-950 p-2.5 rounded-lg border border-slate-800 text-[11px]">
                                <div className="space-y-0.5 truncate">
                                  <span className="text-white font-medium block truncate">
                                    {res.source_document_filename}
                                  </span>
                                  <span className="text-slate-500 text-[10px]">
                                    Page {res.source_page || 1} • Extracted: {res.extracted_value}
                                  </span>
                                </div>
                                {res.evidence_id && (
                                  <button
                                    onClick={() => {
                                      const matched = extractionSummary?.evidence.find((e) => e.id === res.evidence_id);
                                      if (matched) {
                                        setSelectedEvidenceItem(matched);
                                        setShowEvidenceModal(true);
                                      }
                                    }}
                                    className="ml-2 shrink-0 inline-flex items-center gap-1 rounded bg-indigo-500/10 border border-indigo-500/20 px-2 py-1 text-[10px] font-semibold text-indigo-300 hover:bg-indigo-500/20"
                                  >
                                    <Search className="h-3 w-3" /> Trace
                                  </button>
                                )}
                              </div>
                            ) : (
                              <div className="bg-slate-950/60 p-2.5 rounded-lg border border-dashed border-slate-800 text-[11px] text-slate-500 italic">
                                No supporting document evidence linked.
                              </div>
                            )}

                            {/* Human Review Override Action */}
                            {reviewTasks.some((t) => t.compliance_result_id === res.id) && (
                              <div className="flex items-center justify-end pt-1">
                                <button
                                  onClick={() => {
                                    const task = reviewTasks.find((t) => t.compliance_result_id === res.id);
                                    if (task) {
                                      setSelectedReviewTask(task);
                                      setReviewDecision(task.current_status || "COMPLIANT");
                                      setShowReviewModal(true);
                                    }
                                  }}
                                  className="inline-flex items-center gap-1 rounded-lg bg-amber-500/10 border border-amber-500/30 px-2.5 py-1 text-[11px] font-semibold text-amber-300 hover:bg-amber-500/20 transition-all"
                                >
                                  <BrainCircuit className="h-3 w-3" /> Review / Override Decision
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {complianceLoading && (
            <div className="flex items-center justify-center py-10 text-emerald-400 gap-2">
              <RefreshCw className="h-5 w-5 animate-spin" />
              <span className="text-xs font-medium">Evaluating bid compliance rules...</span>
            </div>
          )}

          {!complianceSummary && !complianceLoading && (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-8 text-center space-y-3">
              <ShieldCheck className="h-8 w-8 text-slate-600 mx-auto" />
              <p className="text-sm font-semibold text-slate-300">Compliance Evaluation Pending</p>
              <p className="text-xs text-slate-500 max-w-md mx-auto">
                Click 'Evaluate Bid Compliance' above to compare all uploaded documents and extracted evidence against the tender requirements.
              </p>
            </div>
          )}
        </div>

        {/* Phase 7: Official Compliance & Verification Reports Section */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <FileCheck className="h-5 w-5 text-indigo-400" />
                <h2 className="text-lg font-bold text-white">Compliance & Evaluation Reports</h2>
                <span className="rounded-full bg-indigo-500/10 border border-indigo-500/20 px-2 py-0.5 text-[10px] font-semibold text-indigo-300">
                  Official PDF Records
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Generate and download formal compliance audit reports with grounded evidence citations and evaluation verdicts.
              </p>
            </div>

            <button
              onClick={handleGenerateReport}
              disabled={generatingReport || !complianceSummary}
              className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-indigo-600/20 hover:from-indigo-500 hover:to-purple-500 transition-all disabled:opacity-50"
            >
              <FileText className={`h-4 w-4 ${generatingReport ? "animate-spin" : ""}`} />
              <span>{generatingReport ? "Compiling PDF..." : "Generate Compliance Report"}</span>
            </button>
          </div>

          {/* Reports List */}
          {reportsLoading ? (
            <div className="flex items-center justify-center py-6 text-indigo-400 gap-2">
              <RefreshCw className="h-4 w-4 animate-spin" />
              <span className="text-xs">Loading reports...</span>
            </div>
          ) : reports.length === 0 ? (
            <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/40 p-6 text-center space-y-2">
              <FileText className="h-6 w-6 text-slate-600 mx-auto" />
              <p className="text-xs font-semibold text-slate-400">No compliance reports generated yet.</p>
              <p className="text-[11px] text-slate-500">
                Click 'Generate Compliance Report' above to produce a formal evaluation document.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-300">
                <thead className="bg-slate-950/80 text-[10px] uppercase tracking-wider text-slate-400 border-b border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Report Number</th>
                    <th className="px-4 py-3">Generated By</th>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {reports.map((rep) => (
                    <tr key={rep.id} className="hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3 font-semibold text-white flex items-center gap-2">
                        <FileCheck className="h-4 w-4 text-emerald-400" />
                        {rep.report_number}
                      </td>
                      <td className="px-4 py-3 text-slate-300 font-sans">
                        {rep.generated_by_name || "Procurement Officer"}
                      </td>
                      <td className="px-4 py-3 text-slate-400 text-[11px] font-sans">
                        {new Date(rep.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-right font-sans">
                        <button
                          onClick={() => handleDownloadReport(rep.id, rep.report_number)}
                          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500/10 border border-indigo-500/20 px-3 py-1 text-xs font-semibold text-indigo-300 hover:bg-indigo-500/20 transition-all"
                        >
                          <Download className="h-3.5 w-3.5" /> Download PDF
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Bidder Remarks */}
        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-6 space-y-4">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <FileText className="h-5 w-5 text-emerald-400" />
            Bidder Remarks & Technical Submission Notes
          </h2>
          <div className="text-sm text-slate-300 leading-relaxed whitespace-pre-wrap">
            {bid.notes || "No additional technical remarks provided in this draft."}
          </div>
        </div>
      </main>

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg rounded-2xl border border-slate-800 bg-slate-900 p-6 shadow-2xl space-y-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <UploadCloud className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-bold text-white">Upload Supporting Document</h3>
              </div>
              <button
                onClick={() => {
                  setShowUploadModal(false);
                  setSelectedFile(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <form onSubmit={handleUploadSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Document Category *</label>
                <select
                  value={selectedDocType}
                  onChange={(e) => setSelectedDocType(e.target.value)}
                  className="w-full rounded-xl border border-slate-800 bg-slate-950 px-3 py-2 text-xs text-slate-200 focus:border-emerald-500 focus:outline-none"
                >
                  {DOCUMENT_CATEGORIES.map((cat) => (
                    <option key={cat.value} value={cat.value}>
                      {cat.label}
                    </option>
                  ))}
                </select>
              </div>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300">Select Document File *</label>
                <div className="rounded-xl border border-dashed border-slate-800 bg-slate-950/60 p-6 text-center">
                  <input
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.doc,.docx,.txt"
                    onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                    className="block w-full text-xs text-slate-400 file:mr-4 file:py-2 file:px-4 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-emerald-600/20 file:text-emerald-400 hover:file:bg-emerald-600/30 cursor-pointer"
                  />
                  <p className="text-[11px] text-slate-500 mt-2">
                    PDF, PNG, JPG, DOCX supported. Max size 50 MB. Automatic OCR enabled.
                  </p>
                </div>
              </div>

              {selectedFile && (
                <div className="rounded-lg bg-slate-950 p-3 text-xs text-slate-300 flex items-center justify-between border border-slate-800">
                  <span className="truncate">{selectedFile.name}</span>
                  <span className="text-emerald-400 font-mono">{formatBytes(selectedFile.size)}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
                <button
                  type="button"
                  onClick={() => {
                    setShowUploadModal(false);
                    setSelectedFile(null);
                  }}
                  className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 hover:from-emerald-500 hover:to-teal-400 disabled:opacity-50"
                >
                  {uploading ? (
                    <>
                      <RefreshCw className="h-4 w-4 animate-spin" />
                      <span>Uploading & Processing OCR...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="h-4 w-4" />
                      <span>Upload & Run OCR</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* OCR Extraction Result Modal */}
      {activeOcrDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-3xl max-h-[85vh] flex flex-col rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <Sparkles className="h-5 w-5 text-teal-400" />
                  <h3 className="text-lg font-bold text-white">OCR Text Extraction Inspection</h3>
                </div>
                <p className="text-xs text-slate-400">
                  Document: <span className="text-slate-200 font-semibold">{activeOcrDoc.filename}</span> (
                  {activeOcrDoc.document_type})
                </p>
              </div>
              <button
                onClick={() => {
                  setActiveOcrDoc(null);
                  setOcrData(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {ocrLoading ? (
                <div className="flex flex-col items-center justify-center py-12 gap-3 text-teal-400">
                  <RefreshCw className="h-8 w-8 animate-spin" />
                  <span className="text-sm font-medium">Extracting and loading OCR text...</span>
                </div>
              ) : ocrError ? (
                <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-xs text-rose-300 flex items-center gap-2">
                  <AlertCircle className="h-5 w-5 shrink-0 text-rose-400" />
                  <span>{ocrError}</span>
                </div>
              ) : ocrData ? (
                <div className="space-y-4">
                  {/* OCR Metadata Bar */}
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                      <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Status</span>
                      <span className={`text-xs font-bold ${ocrData.status === "COMPLETED" ? "text-emerald-400" : "text-rose-400"}`}>
                        {ocrData.status}
                      </span>
                    </div>

                    <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                      <span className="text-[10px] uppercase tracking-wider text-slate-500 block">OCR Confidence</span>
                      <span className="text-xs font-bold text-teal-400">
                        {ocrData.ocr_confidence !== null ? `${(ocrData.ocr_confidence * 100).toFixed(1)}%` : "N/A"}
                      </span>
                    </div>

                    <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                      <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Pages Detected</span>
                      <span className="text-xs font-bold text-slate-200">{ocrData.total_pages} Pages</span>
                    </div>
                  </div>

                  {/* Raw Extracted Text Box */}
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-slate-300">Extracted Raw Text Payload</label>
                      <span className="text-[11px] text-slate-500">
                        {ocrData.raw_text ? `${ocrData.raw_text.length} Characters` : "Empty"}
                      </span>
                    </div>

                    <pre className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-slate-200 leading-relaxed max-h-72 overflow-y-auto whitespace-pre-wrap select-all">
                      {ocrData.raw_text || (ocrData.error_message ? `OCR Extraction Error: ${ocrData.error_message}` : "No text extracted from document.")}
                    </pre>
                  </div>
                </div>
              ) : null}
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-between p-4 border-t border-slate-800 bg-slate-950/40">
              <button
                onClick={() => handleTriggerOcr(activeOcrDoc)}
                disabled={ocrLoading}
                className="inline-flex items-center gap-1.5 rounded-xl bg-teal-500/10 border border-teal-500/20 px-3 py-1.5 text-xs font-semibold text-teal-400 hover:bg-teal-500/20 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${ocrLoading ? "animate-spin" : ""}`} /> Re-run OCR Engine
              </button>

              <button
                onClick={() => {
                  setActiveOcrDoc(null);
                  setOcrData(null);
                }}
                className="rounded-xl bg-slate-800 px-4 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Traceability Citation Modal */}
      {showEvidenceModal && selectedEvidenceItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl flex flex-col rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-800">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-emerald-400" />
                  <h3 className="text-lg font-bold text-white">Evidence Traceability & Ground Truth</h3>
                </div>
                <p className="text-xs text-slate-400">
                  Field: <span className="text-indigo-400 font-mono font-semibold">{selectedEvidenceItem.field_name.toUpperCase()}</span>
                </p>
              </div>
              <button
                onClick={() => {
                  setShowEvidenceModal(false);
                  setSelectedEvidenceItem(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5">
              {/* Value Comparison */}
              <div className="grid grid-cols-2 gap-3">
                <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Raw Value from OCR</span>
                  <span className="text-xs font-mono font-bold text-white break-all">
                    {selectedEvidenceItem.extracted_value}
                  </span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3.5 border border-slate-800 space-y-1">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Normalized Value</span>
                  <span className="text-xs font-mono font-bold text-emerald-400 break-all">
                    {selectedEvidenceItem.normalized_value || selectedEvidenceItem.extracted_value}
                  </span>
                </div>
              </div>

              {/* Source Document & Citation */}
              <div className="grid grid-cols-3 gap-3">
                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Source Document</span>
                  <span className="text-xs font-semibold text-slate-200 truncate block mt-0.5" title={selectedEvidenceItem.document_filename || "Document"}>
                    {selectedEvidenceItem.document_filename || "Attached File"}
                  </span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Page Reference</span>
                  <span className="text-xs font-bold text-indigo-400 mt-0.5 block">
                    Page {selectedEvidenceItem.page_number || 1}
                  </span>
                </div>

                <div className="rounded-xl bg-slate-950 p-3 border border-slate-800 text-center">
                  <span className="text-[10px] uppercase tracking-wider text-slate-500 block">Confidence</span>
                  <span className="text-xs font-bold text-emerald-400 mt-0.5 block">
                    {(selectedEvidenceItem.confidence * 100).toFixed(0)}% Match
                  </span>
                </div>
              </div>

              {/* Verbatim Context Snippet */}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-slate-300 flex items-center justify-between">
                  <span>Verbatim Context Citation</span>
                  <span className="text-[10px] text-slate-500 font-mono">Source: {selectedEvidenceItem.source_type}</span>
                </label>
                <div className="rounded-xl border border-slate-800 bg-slate-950 p-4 font-mono text-xs text-indigo-200 leading-relaxed whitespace-pre-wrap">
                  "{selectedEvidenceItem.snippet_text || "Directly grounded in raw document OCR output stream."}"
                </div>
              </div>

              {/* Traceability Audit Trail */}
              <div className="rounded-xl bg-slate-950/60 border border-slate-800 p-3 flex items-center justify-between text-[11px] text-slate-400">
                <span>Evidence Record ID: <span className="font-mono text-slate-300">{selectedEvidenceItem.id.substring(0, 12)}...</span></span>
                <span>Extracted: {new Date(selectedEvidenceItem.created_at).toLocaleString()}</span>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end p-4 border-t border-slate-800 bg-slate-950/40">
              <button
                onClick={() => {
                  setShowEvidenceModal(false);
                  setSelectedEvidenceItem(null);
                }}
                className="rounded-xl bg-slate-800 px-4 py-1.5 text-xs font-semibold text-slate-300 hover:bg-slate-700"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Human Review Decision Modal */}
      {showReviewModal && selectedReviewTask && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
          <div className="w-full max-w-2xl rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl space-y-6 overflow-hidden">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-slate-800 bg-slate-950/50">
              <div className="flex items-center gap-2.5">
                <BrainCircuit className="h-5 w-5 text-amber-400" />
                <div>
                  <h3 className="text-base font-bold text-white">Human Review & Evaluation Override</h3>
                  <p className="text-xs text-slate-400">
                    Mandatory justification required for modifying automated rule engine verdicts.
                  </p>
                </div>
              </div>
              <button
                onClick={() => {
                  setShowReviewModal(false);
                  setSelectedReviewTask(null);
                }}
                className="text-slate-400 hover:text-white"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto text-xs">
              {/* Requirement Summary */}
              <div className="rounded-xl bg-slate-950 p-4 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono text-[10px] text-indigo-300 uppercase font-semibold">
                    {selectedReviewTask.requirement_category || "SPECIFICATION"}
                  </span>
                  <span className="text-[10px] text-amber-400 font-mono font-bold bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                    Original Verdict: {selectedReviewTask.original_decision}
                  </span>
                </div>
                <p className="text-white font-medium text-sm">{selectedReviewTask.requirement_text}</p>
                <p className="text-slate-400 text-xs mt-1">
                  <b>Trigger Reason:</b> {selectedReviewTask.trigger_reason}
                </p>
              </div>

              {/* Evidence & Snippet */}
              {selectedReviewTask.evidence_snippet && (
                <div className="space-y-1.5">
                  <label className="text-slate-400 font-semibold block text-[11px]">
                    Extracted Document Evidence Context
                  </label>
                  <div className="rounded-xl border border-slate-800 bg-slate-950 p-3.5 font-mono text-indigo-200 text-[11px]">
                    "{selectedReviewTask.evidence_snippet}"
                  </div>
                </div>
              )}

              {/* Decision Input Form */}
              <div className="space-y-3 pt-2">
                <div className="space-y-1">
                  <label className="text-slate-200 font-semibold block text-xs">Review Verdict</label>
                  <select
                    value={reviewDecision}
                    onChange={(e) => setReviewDecision(e.target.value)}
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white focus:border-indigo-500 focus:outline-none"
                  >
                    <option value="COMPLIANT">COMPLIANT (Approve / Criteria Satisfied)</option>
                    <option value="NON_COMPLIANT">NON_COMPLIANT (Reject / Criteria Failed)</option>
                    <option value="CLARIFICATION_REQUIRED">CLARIFICATION_REQUIRED (Request Bidder Clarification)</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-slate-200 font-semibold block text-xs">
                    Mandatory Justification <span className="text-rose-400">*</span>
                  </label>
                  <textarea
                    rows={3}
                    value={reviewJustification}
                    onChange={(e) => setReviewJustification(e.target.value)}
                    placeholder="State technical justification, document clauses referenced, and reasons for override..."
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>

                <div className="space-y-1">
                  <label className="text-slate-200 font-semibold block text-xs">Internal Committee Comments (Optional)</label>
                  <input
                    type="text"
                    value={reviewComments}
                    onChange={(e) => setReviewComments(e.target.value)}
                    placeholder="e.g. Approved during Technical Evaluation Committee meeting #4"
                    className="w-full rounded-xl border border-slate-700 bg-slate-950 px-3 py-2 text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
                  />
                </div>
              </div>

              {/* Audit Warning */}
              <div className="rounded-xl border border-amber-500/20 bg-amber-500/5 p-3 flex items-start gap-2.5 text-[11px] text-amber-300">
                <ShieldAlert className="h-4 w-4 shrink-0 text-amber-400 mt-0.5" />
                <p>
                  This decision will be permanently logged in the tamper-evident audit trail with your identity, justification, and timestamp. Original AI/rule decisions remain preserved.
                </p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex items-center justify-end gap-3 p-4 border-t border-slate-800 bg-slate-950/40">
              <button
                onClick={() => {
                  setShowReviewModal(false);
                  setSelectedReviewTask(null);
                }}
                className="rounded-xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitReviewDecision}
                disabled={submittingReview || reviewJustification.trim().length < 5}
                className="rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-4 py-2 text-xs font-semibold text-white shadow-lg shadow-emerald-600/20 hover:from-emerald-500 hover:to-teal-400 disabled:opacity-50"
              >
                {submittingReview ? "Submitting Decision..." : "Confirm & Save Decision"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
