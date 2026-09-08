"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Bell,
  CheckCheck,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Info,
  AlertTriangle,
  ArrowRight,
} from "lucide-react";
import {
  fetchNotificationsApi,
  markAllNotificationsReadApi,
  markNotificationReadApi,
  NotificationItem,
} from "@/lib/api";

export default function NotificationsPage() {
  const [token, setToken] = useState("");
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [unreadCount, setUnreadCount] = useState(0);
  const [filterUnread, setFilterUnread] = useState<boolean | undefined>(undefined);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const sessionToken = localStorage.getItem("token") || "";
    setToken(sessionToken);
    loadNotifs(sessionToken, filterUnread);
  }, [filterUnread]);

  async function loadNotifs(authToken: string, isReadFilter?: boolean) {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchNotificationsApi(authToken || token, isReadFilter, 100, 0);
      setNotifications(data.items);
      setTotal(data.total);
      setUnreadCount(data.unread_count);
    } catch (err: any) {
      setError(err.message || "Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }

  async function handleMarkRead(id: string) {
    if (!token) return;
    try {
      await markNotificationReadApi(id, token);
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      );
      setUnreadCount((prev) => Math.max(0, prev - 1));
    } catch (err: any) {
      alert(`Failed to update notification: ${err.message}`);
    }
  }

  async function handleMarkAllRead() {
    if (!token) return;
    try {
      await markAllNotificationsReadApi(token);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch (err: any) {
      alert(`Failed to mark all as read: ${err.message}`);
    }
  }

  const getIcon = (type: string) => {
    switch (type) {
      case "SUCCESS":
        return <CheckCircle2 className="h-5 w-5 text-emerald-400 shrink-0" />;
      case "WARNING":
      case "ACTION_REQUIRED":
        return <AlertTriangle className="h-5 w-5 text-amber-400 shrink-0" />;
      default:
        return <Info className="h-5 w-5 text-indigo-400 shrink-0" />;
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <main className="mx-auto max-w-5xl px-4 py-8 sm:px-6 lg:px-8 space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-6">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <Bell className="h-6 w-6 text-indigo-400" />
              <h1 className="text-2xl font-bold tracking-tight text-white">Notifications Center</h1>
              {unreadCount > 0 && (
                <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-2.5 py-0.5 text-xs font-bold text-rose-400">
                  {unreadCount} unread
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400">
              Real-time alerts on tenders, bids, AI extraction, compliance evaluations, and review decisions.
            </p>
          </div>

          <div className="flex items-center gap-2">
            {unreadCount > 0 && (
              <button
                onClick={handleMarkAllRead}
                className="inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-3.5 py-2 text-xs font-semibold text-white shadow-md shadow-emerald-500/20 hover:from-emerald-500 hover:to-teal-400"
              >
                <CheckCheck className="h-4 w-4" /> Mark All Read
              </button>
            )}
            <button
              onClick={() => loadNotifs(token, filterUnread)}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800/80 px-3.5 py-2 text-xs font-semibold text-slate-200 hover:bg-slate-800"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} /> Refresh
            </button>
          </div>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-xs font-semibold">
          <button
            onClick={() => setFilterUnread(undefined)}
            className={`px-4 py-2 rounded-xl transition-colors ${
              filterUnread === undefined
                ? "bg-slate-800 text-white border border-slate-700"
                : "text-slate-400 hover:text-white"
            }`}
          >
            All Alerts ({total})
          </button>
          <button
            onClick={() => setFilterUnread(false)}
            className={`px-4 py-2 rounded-xl transition-colors ${
              filterUnread === false
                ? "bg-slate-800 text-white border border-slate-700"
                : "text-slate-400 hover:text-white"
            }`}
          >
            Unread Only ({unreadCount})
          </button>
        </div>

        {/* Notifications List */}
        <div className="space-y-3">
          {loading ? (
            <div className="p-12 text-center text-slate-400 space-y-2">
              <RefreshCw className="h-6 w-6 animate-spin text-indigo-400 mx-auto" />
              <p className="text-xs">Loading notifications...</p>
            </div>
          ) : error ? (
            <div className="p-8 rounded-2xl border border-rose-500/20 bg-rose-500/5 text-center text-rose-400 space-y-2">
              <AlertCircle className="h-6 w-6 mx-auto" />
              <p className="text-xs font-semibold">{error}</p>
            </div>
          ) : notifications.length === 0 ? (
            <div className="p-12 rounded-2xl border border-dashed border-slate-800 bg-slate-900/40 text-center text-slate-500 space-y-2">
              <Bell className="h-8 w-8 mx-auto text-slate-600" />
              <p className="text-sm font-semibold text-slate-400">No notifications found.</p>
              <p className="text-xs text-slate-600">You're caught up with all operational events.</p>
            </div>
          ) : (
            notifications.map((notif) => (
              <div
                key={notif.id}
                className={`rounded-2xl border p-4 sm:p-5 flex items-start gap-4 transition-all shadow-md ${
                  notif.is_read
                    ? "border-slate-800 bg-slate-900/40 opacity-80"
                    : "border-indigo-500/30 bg-slate-900/90 shadow-indigo-950/20"
                }`}
              >
                {getIcon(notif.notification_type)}

                <div className="space-y-1 flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="text-sm font-bold text-white truncate">{notif.title}</h3>
                    <span className="text-[10px] text-slate-500 font-mono whitespace-nowrap">
                      {new Date(notif.created_at).toLocaleString()}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed">{notif.message}</p>

                  <div className="flex items-center justify-between pt-2">
                    {notif.related_resource_type && notif.related_resource_id ? (
                      <Link
                        href={
                          notif.related_resource_type === "bid"
                            ? `/bids/${notif.related_resource_id}`
                            : notif.related_resource_type === "tender"
                            ? `/tenders/${notif.related_resource_id}`
                            : "/dashboard"
                        }
                        className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300"
                      >
                        View Resource <ArrowRight className="h-3 w-3" />
                      </Link>
                    ) : (
                      <span></span>
                    )}

                    {!notif.is_read && (
                      <button
                        onClick={() => handleMarkRead(notif.id)}
                        className="text-[11px] font-semibold text-emerald-400 hover:underline"
                      >
                        Mark as read
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
