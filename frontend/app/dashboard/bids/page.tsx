"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  getCurrentUser,
  getBid,
  getTender,
  getBidDocuments,
  getBidCompliance,
  uploadDocument,
  runDocumentOCR,
  logout,
  type User,
  type Bid,
  type Tender,
  type Document,
  type ComplianceResult,
} from "../../../src/lib/api";

// ============================================================
// PAGE
// ============================================================

export default function BidDetailsPage() {
  const router = useRouter();
  const params = useParams();

  // Safely convert Next.js route parameter to number
  const rawBidId = params?.id;

  const bidId = Array.isArray(rawBidId)
    ? Number(rawBidId[0])
    : Number(rawBidId);

  // ============================================================
  // STATE
  // ============================================================

  const [user, setUser] = useState<User | null>(null);
  const [bid, setBid] = useState<Bid | null>(null);
  const [tender, setTender] = useState<Tender | null>(null);
  const [documents, setDocuments] = useState<Document[]>([]);
  const [compliance, setCompliance] = useState<ComplianceResult[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [uploading, setUploading] = useState(false);
  const [ocrRunning, setOcrRunning] = useState<number | null>(null);

  const [documentType, setDocumentType] = useState(
    "TECHNICAL_DOCUMENT",
  );

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  // ============================================================
  // LOAD BID
  // ============================================================

  useEffect(() => {
    let mounted = true;

    async function loadBid() {
      try {
        setLoading(true);
        setError("");

        // --------------------------------------------------------
        // TOKEN CHECK
        // --------------------------------------------------------

        const token = localStorage.getItem("access_token");

        if (!token) {
          router.replace("/");
          return;
        }

        // --------------------------------------------------------
        // BID ID CHECK
        // --------------------------------------------------------

        if (!bidId || Number.isNaN(bidId)) {
          throw new Error("Invalid bid ID");
        }

        // --------------------------------------------------------
        // CURRENT USER
        // --------------------------------------------------------

        const currentUser = await getCurrentUser();

        if (!mounted) {
          return;
        }

        setUser(currentUser);

        // --------------------------------------------------------
        // BID
        // --------------------------------------------------------

        const bidData = await getBid(bidId);

        if (!mounted) {
          return;
        }

        setBid(bidData);

        // --------------------------------------------------------
        // TENDER
        // --------------------------------------------------------

        if (bidData.tender_id != null) {
          try {
            const tenderData = await getTender(
              Number(bidData.tender_id),
            );

            if (mounted) {
              setTender(tenderData);
            }
          } catch (tenderError) {
            console.warn(
              "Unable to load tender:",
              tenderError,
            );
          }
        }

        // --------------------------------------------------------
        // DOCUMENTS
        // --------------------------------------------------------

        try {
          const documentData =
            await getBidDocuments(bidId);

          if (mounted) {
            setDocuments(
              Array.isArray(documentData)
                ? documentData
                : [],
            );
          }
        } catch (documentError) {
          console.warn(
            "Unable to load documents:",
            documentError,
          );
        }

        // --------------------------------------------------------
        // COMPLIANCE
        // --------------------------------------------------------

        try {
          const complianceData =
            await getBidCompliance(bidId);

          if (mounted) {
            setCompliance(
              Array.isArray(complianceData)
                ? complianceData
                : [],
            );
          }
        } catch (complianceError) {
          console.warn(
            "Unable to load compliance:",
            complianceError,
          );
        }
      } catch (err) {
        console.error(
          "BID DETAILS ERROR:",
          err,
        );

        if (!mounted) {
          return;
        }

        const message =
          err instanceof Error
            ? err.message
            : "Unable to load bid";

        setError(message);

        // --------------------------------------------------------
        // AUTH ERROR
        // --------------------------------------------------------

        const lowerMessage =
          message.toLowerCase();

        if (
          lowerMessage.includes("401") ||
          lowerMessage.includes("unauthorized") ||
          lowerMessage.includes("token") ||
          lowerMessage.includes("expired")
        ) {
          localStorage.removeItem(
            "access_token",
          );

          localStorage.removeItem(
            "token_type",
          );

          router.replace("/");
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    loadBid();

    return () => {
      mounted = false;
    };
  }, [bidId, router]);

  // ============================================================
  // LOGOUT
  // ============================================================

  function handleLogout() {
    logout();
    router.replace("/");
  }

  // ============================================================
  // UPLOAD DOCUMENT
  // ============================================================

  async function handleUpload() {
    if (!selectedFile) {
      alert("Please select a file first.");
      return;
    }

    if (!bidId || Number.isNaN(bidId)) {
      alert("Invalid bid ID.");
      return;
    }

    try {
      setUploading(true);

      const uploaded = await uploadDocument(
        bidId,
        documentType,
        selectedFile,
      );

      setDocuments((previous) => [
        uploaded,
        ...previous,
      ]);

      setSelectedFile(null);

      const fileInput =
        document.getElementById(
          "document-file",
        ) as HTMLInputElement | null;

      if (fileInput) {
        fileInput.value = "";
      }

      alert(
        "Document uploaded successfully.",
      );
    } catch (err) {
      console.error(
        "UPLOAD ERROR:",
        err,
      );

      alert(
        err instanceof Error
          ? err.message
          : "Document upload failed",
      );
    } finally {
      setUploading(false);
    }
  }

  // ============================================================
  // OCR
  // ============================================================

  async function handleOCR(
    documentId: number,
  ) {
    try {
      setOcrRunning(documentId);

      const updatedDocument =
        await runDocumentOCR(documentId);

      setDocuments((previous) =>
        previous.map((document) =>
          document.id === documentId
            ? updatedDocument
            : document,
        ),
      );

      alert(
        "OCR completed successfully.",
      );
    } catch (err) {
      console.error(
        "OCR ERROR:",
        err,
      );

      alert(
        err instanceof Error
          ? err.message
          : "OCR failed",
      );
    } finally {
      setOcrRunning(null);
    }
  }

  // ============================================================
  // LOADING
  // ============================================================

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-950 text-white">
        <div className="text-center">
          <div className="mx-auto mb-4 h-10 w-10 animate-spin rounded-full border-4 border-slate-700 border-t-blue-500" />

          <h2 className="text-lg font-semibold">
            BID SETU
          </h2>

          <p className="mt-2 text-sm text-slate-400">
            Loading bid...
          </p>
        </div>
      </main>
    );
  }

  // ============================================================
  // ERROR
  // ============================================================

  if (error || !bid) {
    return (
      <main className="min-h-screen bg-slate-950 text-white">
        <header className="border-b border-slate-800 bg-slate-900">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link
              href="/dashboard"
              className="text-2xl font-bold hover:text-blue-400"
            >
              BID SETU
            </Link>

            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
            >
              Logout
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-3xl px-6 py-16">
          <div className="rounded-xl border border-red-500/20 bg-red-500/5 p-8 text-center">
            <div className="text-5xl">
              ⚠️
            </div>

            <h1 className="mt-4 text-2xl font-bold">
              Bid Not Found
            </h1>

            <p className="mt-3 text-sm text-slate-400">
              {error ||
                "The requested bid could not be found."}
            </p>

            <Link
              href="/dashboard/bids"
              className="mt-6 inline-flex rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500"
            >
              ← Back to My Bids
            </Link>
          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // STATUS
  // ============================================================

  const status = String(
    bid.status ?? "UNKNOWN",
  ).toUpperCase();

  // ============================================================
  // ROLE
  // ============================================================

  const role = String(
    user?.role ?? "",
  ).toUpperCase();

  const canRunOCR =
    role === "ADMIN" ||
    role === "SUPER_ADMIN" ||
    role === "PROCUREMENT_OFFICER";

  const canUpload =
    role === "BIDDER";

  // ============================================================
  // PAGE
  // ============================================================

  return (
    <main className="min-h-screen bg-slate-950 text-white">

      {/* HEADER */}

      <header className="border-b border-slate-800 bg-slate-900">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">

          <div>
            <Link
              href="/dashboard"
              className="text-2xl font-bold hover:text-blue-400"
            >
              BID SETU
            </Link>

            <p className="text-xs text-slate-400">
              Bid Management
            </p>
          </div>

          <div className="flex items-center gap-5">

            <div className="text-right">
              <p className="text-sm font-semibold">
                {user?.full_name || "User"}
              </p>

              <p className="text-xs text-blue-400">
                {user?.role || "User"}
              </p>
            </div>

            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
            >
              Logout
            </button>

          </div>
        </div>
      </header>

      {/* CONTENT */}

      <div className="mx-auto max-w-7xl px-6 py-8">

        {/* BACK */}

        <Link
          href="/dashboard/bids"
          className="text-sm text-blue-400 hover:text-blue-300"
        >
          ← Back to My Bids
        </Link>

        {/* BID HEADER */}

        <section className="mt-5 rounded-xl border border-slate-800 bg-slate-900 p-6">

          <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">

            <div>

              <div className="flex flex-wrap items-center gap-3">

                <span className="text-xs font-semibold text-blue-400">
                  {bid.bid_number ||
                    `BID-${bid.id}`}
                </span>

                <StatusBadge
                  status={status}
                />

              </div>

              <h1 className="mt-3 text-3xl font-bold">
                {bid.title ||
                  tender?.title ||
                  "Untitled Bid"}
              </h1>

              {bid.description && (
                <p className="mt-3 max-w-3xl text-sm leading-6 text-slate-400">
                  {bid.description}
                </p>
              )}

            </div>

            <div className="rounded-lg border border-slate-700 bg-slate-950 px-5 py-4">

              <p className="text-xs uppercase tracking-wide text-slate-500">
                Bid Status
              </p>

              <p className="mt-1 text-lg font-semibold">
                {status}
              </p>

            </div>

          </div>
        </section>

        {/* TENDER INFORMATION */}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">

          <h2 className="text-xl font-semibold">
            Tender Information
          </h2>

          {tender ? (
            <div className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">

              <InfoItem
                label="Tender Number"
                value={
                  tender.tender_number ||
                  "Not available"
                }
              />

              <InfoItem
                label="Tender Title"
                value={
                  tender.title ||
                  "Not available"
                }
              />

              <InfoItem
                label="Department"
                value={
                  tender.department ||
                  "Not specified"
                }
              />

              <InfoItem
                label="Category"
                value={
                  tender.category ||
                  "Not specified"
                }
              />

              <InfoItem
                label="Estimated Value"
                value={
                  tender.estimated_value != null
                    ? formatCurrency(
                        Number(
                          tender.estimated_value,
                        ),
                      )
                    : "Not specified"
                }
              />

              <InfoItem
                label="Submission Deadline"
                value={
                  tender.submission_deadline
                    ? formatDate(
                        tender.submission_deadline,
                      )
                    : "Not available"
                }
              />

            </div>
          ) : (
            <p className="mt-4 text-sm text-slate-500">
              Tender information is not available.
            </p>
          )}

        </section>

        {/* DOCUMENT UPLOAD */}

        {canUpload && (
          <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">

            <h2 className="text-xl font-semibold">
              Upload Bid Document
            </h2>

            <p className="mt-1 text-sm text-slate-500">
              Upload the documents required for this bid.
            </p>

            <div className="mt-5 grid gap-4 md:grid-cols-3">

              {/* DOCUMENT TYPE */}

              <div>

                <label className="mb-2 block text-sm font-medium text-slate-300">
                  Document Type
                </label>

                <select
                  value={documentType}
                  onChange={(event) =>
                    setDocumentType(
                      event.target.value,
                    )
                  }
                  className="w-full rounded-lg border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none focus:border-blue-500"
                >

                  <option value="TECHNICAL_DOCUMENT">
                    Technical Document
                  </option>

                  <option value="FINANCIAL_DOCUMENT">
                    Financial Document
                  </option>

                  <option value="GST_CERTIFICATE">
                    GST Certificate
                  </option>

                  <option value="PAN_CARD">
                    PAN Card
                  </option>

                  <option value="REGISTRATION_CERTIFICATE">
                    Registration Certificate
                  </option>

                  <option value="EXPERIENCE_CERTIFICATE">
                    Experience Certificate
                  </option>

                  <option value="EMD_DOCUMENT">
                    EMD Document
                  </option>

                  <option value="OTHER">
                    Other
                  </option>

                </select>
              </div>

              {/* FILE */}

              <div>

                <label className="mb-2 block text-sm font-medium text-slate-300">
                  Select File
                </label>

                <input
                  id="document-file"
                  type="file"
                  accept=".pdf,.png,.jpg,.jpeg"
                  onChange={(event) =>
                    setSelectedFile(
                      event.target.files?.[0] ||
                        null,
                    )
                  }
                  className="block w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2.5 text-sm text-slate-300 file:mr-3 file:rounded-md file:border-0 file:bg-slate-800 file:px-3 file:py-2 file:text-sm file:text-white"
                />

              </div>

              {/* BUTTON */}

              <div className="flex items-end">

                <button
                  type="button"
                  onClick={handleUpload}
                  disabled={
                    uploading ||
                    !selectedFile
                  }
                  className="w-full rounded-lg bg-blue-600 px-5 py-3 text-sm font-semibold transition hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {uploading
                    ? "Uploading..."
                    : "Upload Document"}
                </button>

              </div>

            </div>

            {selectedFile && (
              <p className="mt-3 text-xs text-slate-500">
                Selected:{" "}
                {selectedFile.name}
              </p>
            )}

          </section>
        )}

        {/* DOCUMENTS */}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">

          <div className="flex items-center justify-between">

            <div>

              <h2 className="text-xl font-semibold">
                Bid Documents
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Uploaded documents and verification status.
              </p>

            </div>

            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
              {documents.length}{" "}
              {documents.length === 1
                ? "Document"
                : "Documents"}
            </span>

          </div>

          {documents.length === 0 ? (

            <div className="mt-6 rounded-lg border border-dashed border-slate-700 p-10 text-center">

              <div className="text-4xl">
                📄
              </div>

              <h3 className="mt-3 font-semibold">
                No documents uploaded
              </h3>

              <p className="mt-1 text-sm text-slate-500">
                Required bid documents will appear here.
              </p>

            </div>

          ) : (

            <div className="mt-6 space-y-4">

              {documents.map((document) => {

                const verification =
                  String(
                    document.verification_status ??
                      "PENDING",
                  ).toUpperCase();

                const isPdf =
                  document.mime_type ===
                  "application/pdf";

                return (
                  <div
                    key={document.id}
                    className="rounded-lg border border-slate-800 bg-slate-950 p-5"
                  >

                    <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">

                      <div className="min-w-0">

                        <div className="flex flex-wrap items-center gap-3">

                          <h3 className="break-all font-semibold">
                            {document.file_name}
                          </h3>

                          <VerificationBadge
                            status={verification}
                          />

                        </div>

                        <div className="mt-2 grid gap-2 text-xs text-slate-500 sm:grid-cols-2 lg:grid-cols-4">

                          <span>
                            Type:{" "}
                            {document.document_type ||
                              "Unknown"}
                          </span>

                          <span>
                            Size:{" "}
                            {formatFileSize(
                              document.file_size,
                            )}
                          </span>

                          <span>
                            MIME:{" "}
                            {document.mime_type ||
                              "Unknown"}
                          </span>

                          <span className="break-all">
                            Hash:{" "}
                            {document.file_hash
                              ? `${document.file_hash.slice(
                                  0,
                                  12,
                                )}...`
                              : "N/A"}
                          </span>

                        </div>

                      </div>

                      {/* OCR */}

                      {canRunOCR && isPdf && (
                        <button
                          type="button"
                          onClick={() =>
                            handleOCR(
                              document.id,
                            )
                          }
                          disabled={
                            ocrRunning ===
                            document.id
                          }
                          className="shrink-0 rounded-lg bg-purple-600 px-4 py-2.5 text-sm font-medium hover:bg-purple-500 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {ocrRunning ===
                          document.id
                            ? "Running OCR..."
                            : "Run OCR"}
                        </button>
                      )}

                    </div>

                    {/* OCR TEXT */}

                    {document.extracted_text && (
                      <div className="mt-5 border-t border-slate-800 pt-4">

                        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                          Extracted Text
                        </p>

                        <div className="mt-2 max-h-64 overflow-auto rounded-lg bg-slate-900 p-4">

                          <pre className="whitespace-pre-wrap break-words text-xs leading-5 text-slate-300">
                            {document.extracted_text}
                          </pre>

                        </div>

                      </div>
                    )}

                  </div>
                );
              })}

            </div>
          )}

        </section>

        {/* COMPLIANCE */}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">

          <div className="flex items-center justify-between">

            <div>

              <h2 className="text-xl font-semibold">
                Compliance Verification
              </h2>

              <p className="mt-1 text-sm text-slate-500">
                Requirement-wise compliance results.
              </p>

            </div>

            <span className="rounded-full bg-slate-800 px-3 py-1 text-xs text-slate-300">
              {compliance.length} Results
            </span>

          </div>

          {compliance.length === 0 ? (

            <div className="mt-6 rounded-lg border border-dashed border-slate-700 p-8 text-center">

              <div className="text-3xl">
                🔍
              </div>

              <p className="mt-3 text-sm text-slate-400">
                No compliance results available yet.
              </p>

            </div>

          ) : (

            <div className="mt-6 space-y-3">

              {compliance.map(
                (result, index) => {

                  const resultStatus =
                    String(
                      result.status ??
                        "PENDING",
                    ).toUpperCase();

                  return (
                    <div
                      key={
                        result.id ??
                        `${result.requirement_id}-${index}`
                      }
                      className="rounded-lg border border-slate-800 bg-slate-950 p-4"
                    >

                      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">

                        <div>

                          <p className="text-sm font-semibold">
                            Requirement{" "}
                            {result.requirement_id ??
                              "N/A"}
                          </p>

                          {result.reason && (
                            <p className="mt-1 text-sm text-slate-500">
                              {result.reason}
                            </p>
                          )}

                        </div>

                        <div className="flex items-center gap-3">

                          {result.score != null && (
                            <span className="text-sm text-slate-400">
                              Score:{" "}
                              {result.score}
                            </span>
                          )}

                          <VerificationBadge
                            status={
                              resultStatus
                            }
                          />

                        </div>

                      </div>

                    </div>
                  );
                },
              )}

            </div>
          )}

        </section>

      </div>
    </main>
  );
}

// ============================================================
// INFO ITEM
// ============================================================

function InfoItem({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-wide text-slate-500">
        {label}
      </p>

      <p className="mt-1 text-sm text-slate-300">
        {value}
      </p>
    </div>
  );
}

// ============================================================
// STATUS BADGE
// ============================================================

function StatusBadge({
  status,
}: {
  status: string;
}) {
  const normalized =
    status.toUpperCase();

  let className =
    "bg-slate-800 text-slate-300";

  if (normalized === "SUBMITTED") {
    className =
      "bg-blue-500/10 text-blue-400";
  } else if (
    normalized === "APPROVED"
  ) {
    className =
      "bg-green-500/10 text-green-400";
  } else if (
    normalized === "REJECTED"
  ) {
    className =
      "bg-red-500/10 text-red-400";
  } else if (
    normalized === "DRAFT"
  ) {
    className =
      "bg-yellow-500/10 text-yellow-400";
  } else if (
    normalized === "UNDER_REVIEW"
  ) {
    className =
      "bg-purple-500/10 text-purple-400";
  }

  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${className}`}
    >
      {normalized}
    </span>
  );
}

// ============================================================
// VERIFICATION BADGE
// ============================================================

function VerificationBadge({
  status,
}: {
  status: string;
}) {
  const normalized =
    status.toUpperCase();

  let className =
    "bg-slate-800 text-slate-300";

  if (
    normalized === "VERIFIED" ||
    normalized === "COMPLIANT" ||
    normalized === "PASS" ||
    normalized === "APPROVED"
  ) {
    className =
      "bg-green-500/10 text-green-400";
  } else if (
    normalized === "FAILED" ||
    normalized === "NON_COMPLIANT" ||
    normalized === "FAIL" ||
    normalized === "REJECTED"
  ) {
    className =
      "bg-red-500/10 text-red-400";
  } else if (
    normalized === "PENDING"
  ) {
    className =
      "bg-yellow-500/10 text-yellow-400";
  } else if (
    normalized === "UNDER_REVIEW"
  ) {
    className =
      "bg-purple-500/10 text-purple-400";
  }

  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-medium ${className}`}
    >
      {normalized}
    </span>
  );
}

// ============================================================
// DATE
// ============================================================

function formatDate(
  value: string,
): string {
  try {
    return new Date(
      value,
    ).toLocaleString("en-IN", {
      dateStyle: "medium",
      timeStyle: "short",
    });
  } catch {
    return value;
  }
}

// ============================================================
// CURRENCY
// ============================================================

function formatCurrency(
  value: number,
): string {
  try {
    return new Intl.NumberFormat(
      "en-IN",
      {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
      },
    ).format(value);
  } catch {
    return `₹${value}`;
  }
}

// ============================================================
// FILE SIZE
// ============================================================

function formatFileSize(
  value?: number | null,
): string {
  if (value == null || value === 0) {
    return "Unknown";
  }

  if (value < 1024) {
    return `${value} B`;
  }

  if (value < 1024 * 1024) {
    return `${(value / 1024).toFixed(1)} KB`;
  }

  return `${(
    value /
    (1024 * 1024)
  ).toFixed(1)} MB`;
}