"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ShieldCheck,
  FileText,
  Send,
  PlusCircle,
  LayoutDashboard,
  Bell,
  CheckCheck,
  ExternalLink,
  History,
  LogIn,
  LogOut,
} from "lucide-react";
import {
  fetchNotificationsApi,
  fetchUnreadNotificationCountApi,
  markAllNotificationsReadApi,
  markNotificationReadApi,
  NotificationItem,
  logoutApi,
  fetchCurrentUserApi,
} from "@/lib/api";

export default function Navigation() {
  const pathname = usePathname();
  const router = useRouter();
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");
  const [unreadCount, setUnreadCount] = useState(0);
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [showNotifsDropdown, setShowNotifsDropdown] = useState(false);
  const [loadingNotifs, setLoadingNotifs] = useState(false);

  const navItems = [
    { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ["ADMIN", "PROCUREMENT_OFFICER", "BIDDER", "REVIEWER", "AUDITOR"] },
    { href: "/tenders", label: "Tenders", icon: FileText, roles: ["ADMIN", "PROCUREMENT_OFFICER", "BIDDER", "REVIEWER", "AUDITOR"] },
    { href: "/bids", label: role === "PROCUREMENT_OFFICER" ? "Bid Evaluation" : role === "BIDDER" ? "My Bids" : "Bids", icon: Send, roles: ["ADMIN", "PROCUREMENT_OFFICER", "BIDDER", "REVIEWER", "AUDITOR"] },
    { href: "/audit-logs", label: "Audit Trail", icon: History, roles: ["ADMIN", "AUDITOR"] },
  ];

  useEffect(() => {
    const storedToken = localStorage.getItem("token");
    if (!storedToken) return;
    const sessionToken = storedToken;
    setToken(sessionToken);
    async function initializeSession() {
      try {
        const currentUser = await fetchCurrentUserApi(sessionToken);
        const verifiedRole = currentUser.roles[0] || "";
        setRole(verifiedRole);
        localStorage.setItem("user_role", verifiedRole);
        const data = await fetchUnreadNotificationCountApi(sessionToken);
        setUnreadCount(data.unread_count);
      } catch {
        localStorage.removeItem("token");
        localStorage.removeItem("user_email");
        localStorage.removeItem("user_role");
        setToken("");
        setRole("");
      }
    }
    initializeSession();
  }, []);

  async function handleLogout() {
    if (token) await logoutApi(token).catch(() => undefined);
    localStorage.removeItem("token");
    localStorage.removeItem("user_email");
    localStorage.removeItem("user_role");
    setToken("");
    setRole("");
    setShowNotifsDropdown(false);
    router.push("/login");
  }

  const canCreateTender = role === "ADMIN" || role === "PROCUREMENT_OFFICER";
  const visibleNavItems = navItems.filter((item) => role === "ADMIN" || item.roles.includes(role));

  async function loadUnread(authToken: string) {
    try {
      const data = await fetchUnreadNotificationCountApi(authToken || token);
      setUnreadCount(data.unread_count);
    } catch {}
  }

  async function loadRecentNotifications() {
    if (!token) return;
    setLoadingNotifs(true);
    try {
      const data = await fetchNotificationsApi(token, undefined, 5, 0);
      setNotifications(data.items);
      setUnreadCount(data.unread_count);
    } catch {}
    finally {
      setLoadingNotifs(false);
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
    } catch {}
  }

  async function handleMarkAllRead() {
    if (!token) return;
    try {
      await markAllNotificationsReadApi(token);
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })));
      setUnreadCount(0);
    } catch {}
  }

  return (
    <header className="sticky top-0 z-50 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
        {/* Brand */}
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-400 text-white shadow-lg shadow-emerald-500/20 group-hover:scale-105 transition-transform">
            <ShieldCheck className="h-5 w-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-bold text-base text-slate-100 tracking-tight">BIDVERIFY AI</span>
              <span className="rounded bg-emerald-500/10 px-1.5 py-0.2 text-[9px] font-semibold text-emerald-400 border border-emerald-500/20">
                PRO
              </span>
            </div>
            <p className="text-[10px] text-slate-400">Compliance & Trust Engine</p>
          </div>
        </Link>

        {/* Links */}
        <nav className="flex items-center gap-1 sm:gap-1.5">
          {visibleNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href || (item.href !== "/dashboard" && pathname.startsWith(item.href));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-slate-800 text-emerald-400 border border-slate-700 font-semibold"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-200"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                <span className="hidden md:inline">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        {/* Right Actions & Notification Bell */}
        <div className="flex items-center gap-3">
          {!token && (
            <Link href="/login" className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-400 hover:bg-emerald-500/20">
              <LogIn className="h-4 w-4" /> Sign in
            </Link>
          )}
          {token && (
            <button onClick={handleLogout} className="inline-flex items-center gap-1.5 rounded-xl border border-slate-700 bg-slate-800 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white" aria-label="Log out">
              <LogOut className="h-4 w-4" /> <span className="hidden md:inline">Logout</span>
            </button>
          )}
          {/* Notification Bell */}
          <div className="relative">
            <button
              onClick={() => {
                const next = !showNotifsDropdown;
                setShowNotifsDropdown(next);
                if (next) loadRecentNotifications();
              }}
              className="relative rounded-xl border border-slate-700 bg-slate-800/80 p-2 text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
              aria-label="Notifications"
            >
              <Bell className="h-4 w-4" />
              {unreadCount > 0 && (
                <span className="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-rose-500 px-1 text-[9px] font-bold text-white shadow-lg animate-pulse">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {/* Notification Dropdown */}
            {showNotifsDropdown && (
              <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-2xl border border-slate-800 bg-slate-900 shadow-2xl z-50 overflow-hidden">
                <div className="flex items-center justify-between p-3.5 border-b border-slate-800 bg-slate-950/60">
                  <div className="flex items-center gap-2">
                    <Bell className="h-4 w-4 text-indigo-400" />
                    <span className="text-xs font-bold text-white">Notifications</span>
                    {unreadCount > 0 && (
                      <span className="rounded-full bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.2 text-[10px] font-bold text-rose-400">
                        {unreadCount} unread
                      </span>
                    )}
                  </div>
                  {unreadCount > 0 && (
                    <button
                      onClick={handleMarkAllRead}
                      className="flex items-center gap-1 text-[11px] font-semibold text-emerald-400 hover:text-emerald-300"
                    >
                      <CheckCheck className="h-3 w-3" /> Mark all read
                    </button>
                  )}
                </div>

                <div className="max-h-72 overflow-y-auto divide-y divide-slate-800/60 text-xs">
                  {loadingNotifs ? (
                    <div className="p-4 text-center text-slate-500 text-xs">Loading alerts...</div>
                  ) : notifications.length === 0 ? (
                    <div className="p-6 text-center text-slate-500 text-xs space-y-1">
                      <p>No notifications yet</p>
                      <p className="text-[10px] text-slate-600">You're completely up to date.</p>
                    </div>
                  ) : (
                    notifications.map((notif) => (
                      <div
                        key={notif.id}
                        className={`p-3 space-y-1 hover:bg-slate-800/40 transition-colors ${
                          notif.is_read ? "opacity-75" : "bg-indigo-950/20"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="font-semibold text-white text-xs">{notif.title}</h4>
                          {!notif.is_read && (
                            <button
                              onClick={() => handleMarkRead(notif.id)}
                              className="text-[10px] text-indigo-400 hover:underline shrink-0"
                            >
                              Mark read
                            </button>
                          )}
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed">{notif.message}</p>
                        <span className="text-[9px] text-slate-500 block pt-0.5 font-mono">
                          {new Date(notif.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                    ))
                  )}
                </div>

                <div className="p-2 border-t border-slate-800 bg-slate-950 text-center">
                  <Link
                    href="/notifications"
                    onClick={() => setShowNotifsDropdown(false)}
                    className="inline-flex items-center gap-1 text-[11px] font-semibold text-indigo-400 hover:text-indigo-300"
                  >
                    View All Notifications <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            )}
          </div>

          {canCreateTender && (
            <Link
              href="/tenders/new"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-500 px-3 py-1.5 text-xs font-semibold text-white shadow-md shadow-emerald-500/20 hover:from-emerald-500 hover:to-teal-400 transition-all"
            >
              <PlusCircle className="h-3.5 w-3.5" />
              <span>Create Tender</span>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
