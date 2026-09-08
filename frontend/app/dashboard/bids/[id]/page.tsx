"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";

import {
  fetchCurrentUserApi,
  fetchBidById,
  fetchTenderById,
  fetchBidDocumentsApi,
  fetchBidComplianceSummaryApi,
  logoutApi,
} from "@/lib/api";

export default function BidDetailsPage() {
  const router = useRouter();
  const params = useParams();

  const bidId = Number(params.id);

  const [user, setUser] = useState<any>(null);
  const [bid, setBid] = useState<any>(null);
  const [tender, setTender] = useState<any>(null);
  const [documents, setDocuments] = useState<any[]>([]);
  const [compliance, setCompliance] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // ============================================================
  // LOAD BID DETAILS
  // ============================================================

  useEffect(() => {
    let mounted = true;

    async function loadBid() {
      try {
        setLoading(true);
        setError("");

        const token = localStorage.getItem("access_token");

        if (!token) {
          router.replace("/");
          return;
        }

        if (!Number.isInteger(bidId) || bidId <= 0) {
          throw new Error("Invalid bid ID");
        }

        // --------------------------------------------------------
        // CURRENT USER
        // --------------------------------------------------------

        let currentUser: any = null;

        try {
          currentUser = await fetchCurrentUserApi(token);
        } catch (err) {
          console.warn("Could not load current user:", err);
        }

        if (!mounted) return;

        setUser(currentUser);

        // --------------------------------------------------------
        // BID
        // --------------------------------------------------------

        const bidData = await fetchBidById(
          String(bidId),
          token,
        );

        if (!mounted) return;

        setBid(bidData);

        // --------------------------------------------------------
        // TENDER
        // --------------------------------------------------------

        if (bidData?.tender_id != null) {
          try {
            const tenderData = await fetchTenderById(
              String(bidData.tender_id),
              token,
            );

            if (mounted) {
              setTender(tenderData);
            }
          } catch (err) {
            console.warn(
              "Could not load tender:",
              err,
            );
          }
        }

        // --------------------------------------------------------
        // DOCUMENTS
        // --------------------------------------------------------

        try {
          const documentData =
            await fetchBidDocumentsApi(
              String(bidId),
              token,
            );

          if (mounted) {
            setDocuments(
              Array.isArray(documentData)
                ? documentData
                : documentData?.items ?? [],
            );
          }
        } catch (err) {
          console.warn(
            "Could not load documents:",
            err,
          );
        }

        // --------------------------------------------------------
        // COMPLIANCE
        // --------------------------------------------------------

        try {
          const complianceData =
            await fetchBidComplianceSummaryApi(
              String(bidId),
              token,
            );

          if (mounted) {
            setCompliance(complianceData);
          }
        } catch (err) {
          console.warn(
            "Could not load compliance:",
            err,
          );
        }
      } catch (err) {
        console.error(
          "BID DETAILS ERROR:",
          err,
        );

        if (!mounted) return;

        const message =
          err instanceof Error
            ? err.message
            : "Unable to load bid";

        setError(message);

        // --------------------------------------------------------
        // TOKEN EXPIRED
        // --------------------------------------------------------

        if (
          message.includes("401") ||
          message
            .toLowerCase()
            .includes("unauthorized") ||
          message
            .toLowerCase()
            .includes("token") ||
          message
            .toLowerCase()
            .includes("authentication")
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

  async function handleLogout() {
    const token =
      localStorage.getItem("access_token");

    try {
      if (token) {
        await logoutApi(token);
      }
    } catch (err) {
      console.warn(
        "Logout API failed:",
        err,
      );
    } finally {
      localStorage.removeItem(
        "access_token",
      );

      localStorage.removeItem(
        "token_type",
      );

      router.replace("/");
    }
  }

  // ============================================================
  // HELPERS
  // ============================================================

  function formatDate(
    value: string | null | undefined,
  ) {
    if (!value) return "—";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
      return value;
    }

    return date.toLocaleString();
  }

  function getStatusClass(
    status: string | null | undefined,
  ) {
    const value =
      String(status ?? "").toUpperCase();

    if (
      value === "COMPLIANT" ||
      value === "VERIFIED" ||
      value === "APPROVED" ||
      value === "COMPLETED"
    ) {
      return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    }

    if (
      value === "NON_COMPLIANT" ||
      value === "FAILED" ||
      value === "REJECTED"
    ) {
      return "bg-red-500/10 text-red-400 border-red-500/30";
    }

    if (
      value === "PROCESSING" ||
      value === "UNDER_REVIEW" ||
      value === "PENDING"
    ) {
      return "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
    }

    return "bg-slate-800 text-slate-300 border-slate-700";
  }

  function getComplianceStatus() {
    if (!compliance) {
      return "NOT AVAILABLE";
    }

    return (
      compliance.status ??
      compliance.compliance_status ??
      compliance.result ??
      compliance.decision ??
      "AVAILABLE"
    );
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
            Loading bid details...
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
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
            >
              Logout
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-3xl px-6 py-16">
          <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-8 text-center">
            <div className="text-4xl">
              ⚠️
            </div>

            <h1 className="mt-4 text-2xl font-bold">
              Unable to open bid
            </h1>

            <p className="mt-3 text-sm text-red-300">
              {error || "Bid not found"}
            </p>

            <div className="mt-6 flex justify-center gap-3">
              <Link
                href="/dashboard/bids"
                className="rounded-lg border border-slate-700 px-5 py-3 text-sm font-medium hover:bg-slate-800"
              >
                Back to Bids
              </Link>

              <button
                onClick={() =>
                  window.location.reload()
                }
                className="rounded-lg bg-blue-600 px-5 py-3 text-sm font-medium hover:bg-blue-500"
              >
                Try Again
              </button>
            </div>
          </div>
        </div>
      </main>
    );
  }

  // ============================================================
  // MAIN PAGE
  // ============================================================

  const complianceStatus =
    getComplianceStatus();

  return (
    <main className="min-h-screen bg-slate-950 text-white">
      {/* ====================================================== */}
      {/* HEADER */}
      {/* ====================================================== */}

      <header className="sticky top-0 z-20 border-b border-slate-800 bg-slate-950/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-6">
            <Link
              href="/dashboard"
              className="text-2xl font-bold tracking-tight hover:text-blue-400"
            >
              BID SETU
            </Link>

            <span className="hidden text-sm text-slate-500 md:block">
              /
            </span>

            <Link
              href="/dashboard/bids"
              className="hidden text-sm text-slate-400 hover:text-white md:block"
            >
              Bids
            </Link>

            <span className="hidden text-sm text-slate-500 md:block">
              /
            </span>

            <span className="hidden text-sm text-slate-300 md:block">
              Bid Details
            </span>
          </div>

          <div className="flex items-center gap-4">
            {user && (
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium text-white">
                  {user.name ??
                    user.full_name ??
                    user.email ??
                    "User"}
                </p>

                <p className="text-xs text-slate-500">
                  {user.role ??
                    user.role_name ??
                    ""}
                </p>
              </div>
            )}

            <button
              onClick={handleLogout}
              className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      {/* ====================================================== */}
      {/* CONTENT */}
      {/* ====================================================== */}

      <div className="mx-auto max-w-7xl px-6 py-8">
        {/* ---------------------------------------------------- */}
        {/* BACK */}
        {/* ---------------------------------------------------- */}

        <Link
          href="/dashboard/bids"
          className="mb-6 inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white"
        >
          ← Back to Bids
        </Link>

        {/* ---------------------------------------------------- */}
        {/* TITLE */}
        {/* ---------------------------------------------------- */}

        <section className="mb-8">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-3">
                <span className="rounded-md border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-xs font-semibold text-blue-400">
                  BID #{bid.id}
                </span>

                <span
                  className={`rounded-md border px-3 py-1 text-xs font-semibold ${getStatusClass(
                    bid.status,
                  )}`}
                >
                  {bid.status ??
                    "UNKNOWN"}
                </span>
              </div>

              <h1 className="text-3xl font-bold tracking-tight">
                {bid.bid_number ??
                  `Bid ${bid.id}`}
              </h1>

              <p className="mt-2 text-slate-400">
                Bid submission and compliance
                details
              </p>
            </div>

            <div className="flex gap-3">
              <Link
                href={`/dashboard/bids/${bidId}`}
                className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:bg-slate-800"
              >
                Refresh Page
              </Link>
            </div>
          </div>
        </section>

        {/* ==================================================== */}
        {/* BID + TENDER SUMMARY */}
        {/* ==================================================== */}

        <section className="grid gap-6 lg:grid-cols-2">
          {/* -------------------------------------------------- */}
          {/* BID INFORMATION */}
          {/* -------------------------------------------------- */}

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold">
              Bid Information
            </h2>

            <div className="mt-5 space-y-4">
              <InfoRow
                label="Bid ID"
                value={String(
                  bid.id ?? "—",
                )}
              />

              <InfoRow
                label="Bid Number"
                value={
                  bid.bid_number ?? "—"
                }
              />

              <InfoRow
                label="Bidder ID"
                value={String(
                  bid.bidder_id ?? "—",
                )}
              />

              <InfoRow
                label="Status"
                value={
                  bid.status ?? "—"
                }
              />

              <InfoRow
                label="Submission Date"
                value={formatDate(
                  bid.submission_date,
                )}
              />

              <InfoRow
                label="Created"
                value={formatDate(
                  bid.created_at,
                )}
              />

              <InfoRow
                label="Last Updated"
                value={formatDate(
                  bid.updated_at,
                )}
              />
            </div>
          </div>

          {/* -------------------------------------------------- */}
          {/* TENDER INFORMATION */}
          {/* -------------------------------------------------- */}

          <div className="rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold">
              Tender Information
            </h2>

            {tender ? (
              <div className="mt-5 space-y-4">
                <InfoRow
                  label="Tender Number"
                  value={
                    tender.tender_number ??
                    tender.number ??
                    "—"
                  }
                />

                <InfoRow
                  label="Title"
                  value={
                    tender.title ?? "—"
                  }
                />

                <InfoRow
                  label="Organization"
                  value={
                    tender.organization ??
                    "—"
                  }
                />

                <InfoRow
                  label="Category"
                  value={
                    tender.category ?? "—"
                  }
                />

                <InfoRow
                  label="Deadline"
                  value={formatDate(
                    tender.submission_deadline ??
                      tender.deadline,
                  )}
                />

                <InfoRow
                  label="Status"
                  value={
                    tender.status ?? "—"
                  }
                />
              </div>
            ) : (
              <div className="mt-5 rounded-lg border border-slate-800 bg-slate-950 p-5 text-sm text-slate-400">
                Tender information could not
                be loaded.
              </div>
            )}
          </div>
        </section>

        {/* ==================================================== */}
        {/* COMPLIANCE */}
        {/* ==================================================== */}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div>
              <h2 className="text-lg font-semibold">
                Compliance Verification
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Current compliance result for
                this bid
              </p>
            </div>

            <span
              className={`rounded-lg border px-4 py-2 text-sm font-semibold ${getStatusClass(
                String(complianceStatus),
              )}`}
            >
              {String(
                complianceStatus,
              ).replaceAll("_", " ")}
            </span>
          </div>

          {compliance ? (
            <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                title="Status"
                value={String(
                  complianceStatus,
                )}
              />

              <StatCard
                title="Total Requirements"
                value={String(
                  compliance.total_requirements ??
                    compliance.total ??
                    compliance.requirements_count ??
                    "—",
                )}
              />

              <StatCard
                title="Compliant"
                value={String(
                  compliance.compliant_count ??
                    compliance.compliant ??
                    "—",
                )}
              />

              <StatCard
                title="Non-Compliant"
                value={String(
                  compliance.non_compliant_count ??
                    compliance.non_compliant ??
                    "—",
                )}
              />
            </div>
          ) : (
            <div className="mt-5 rounded-lg border border-slate-800 bg-slate-950 p-5 text-sm text-slate-400">
              Compliance information is not
              available yet.
            </div>
          )}
        </section>

        {/* ==================================================== */}
        {/* DOCUMENTS */}
        {/* ==================================================== */}

        <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold">
                Bid Documents
              </h2>

              <p className="mt-1 text-sm text-slate-400">
                Documents submitted with this
                bid
              </p>
            </div>

            <span className="rounded-full bg-slate-800 px-3 py-1 text-sm text-slate-300">
              {documents.length}{" "}
              {documents.length === 1
                ? "Document"
                : "Documents"}
            </span>
          </div>

          <div className="mt-6">
            {documents.length === 0 ? (
              <div className="rounded-lg border border-dashed border-slate-700 bg-slate-950 p-8 text-center">
                <div className="text-3xl">
                  📄
                </div>

                <h3 className="mt-3 font-medium">
                  No documents found
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  No documents have been
                  submitted for this bid.
                </p>
              </div>
            ) : (
              <div className="overflow-hidden rounded-lg border border-slate-800">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-sm">
                    <thead className="bg-slate-950 text-xs uppercase text-slate-500">
                      <tr>
                        <th className="px-5 py-4">
                          Document
                        </th>

                        <th className="px-5 py-4">
                          Type
                        </th>

                        <th className="px-5 py-4">
                          Status
                        </th>

                        <th className="px-5 py-4">
                          Size
                        </th>

                        <th className="px-5 py-4">
                          Uploaded
                        </th>
                      </tr>
                    </thead>

                    <tbody className="divide-y divide-slate-800">
                      {documents.map(
                        (
                          document: any,
                          index: number,
                        ) => (
                          <tr
                            key={
                              document.id ??
                              index
                            }
                            className="hover:bg-slate-950/70"
                          >
                            <td className="px-5 py-4">
                              <div className="font-medium text-white">
                                {document.file_name ??
                                  document.filename ??
                                  `Document ${
                                    index + 1
                                  }`}
                              </div>

                              {document.mime_type && (
                                <div className="mt-1 text-xs text-slate-500">
                                  {
                                    document.mime_type
                                  }
                                </div>
                              )}
                            </td>

                            <td className="px-5 py-4 text-slate-300">
                              {document.document_type ??
                                "—"}
                            </td>

                            <td className="px-5 py-4">
                              <span
                                className={`rounded-md border px-2.5 py-1 text-xs font-medium ${getStatusClass(
                                  document.verification_status,
                                )}`}
                              >
                                {(
                                  document.verification_status ??
                                  "PENDING"
                                ).replaceAll(
                                  "_",
                                  " ",
                                )}
                              </span>
                            </td>

                            <td className="px-5 py-4 text-slate-400">
                              {document.file_size
                                ? `${(
                                    document.file_size /
                                    1024
                                  ).toFixed(
                                    1,
                                  )} KB`
                                : "—"}
                            </td>

                            <td className="px-5 py-4 text-slate-400">
                              {formatDate(
                                document.created_at,
                              )}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </section>

        {/* ==================================================== */}
        {/* NOTES */}
        {/* ==================================================== */}

        {bid.notes && (
          <section className="mt-6 rounded-xl border border-slate-800 bg-slate-900 p-6">
            <h2 className="text-lg font-semibold">
              Bidder Notes
            </h2>

            <p className="mt-4 whitespace-pre-wrap rounded-lg bg-slate-950 p-5 text-sm leading-7 text-slate-300">
              {bid.notes}
            </p>
          </section>
        )}

        {/* ==================================================== */}
        {/* FOOTER */}
        {/* ==================================================== */}

        <div className="mt-10 border-t border-slate-800 pt-6 text-center text-xs text-slate-600">
          BID SETU • Integrated Bid Compliance
          Verification Platform
        </div>
      </div>
    </main>
  );
}

// ============================================================
// INFO ROW
// ============================================================

function InfoRow({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="flex flex-col gap-1 border-b border-slate-800 pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <span className="text-sm text-slate-500">
        {label}
      </span>

      <span className="break-words text-sm font-medium text-slate-200 sm:text-right">
        {value}
      </span>
    </div>
  );
}

// ============================================================
// STAT CARD
// ============================================================

function StatCard({
  title,
  value,
}: {
  title: string;
  value: string;
}) {
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950 p-5">
      <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
        {title}
      </p>

      <p className="mt-2 text-xl font-bold text-white">
        {value}
      </p>
    </div>
  );
}