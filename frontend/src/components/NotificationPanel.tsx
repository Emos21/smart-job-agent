import { useState, useEffect } from "react";
import { Bell, Target, ClipboardList, CheckCheck, X } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { Notification } from "../types";

interface NotificationPanelProps {
  onClose: () => void;
  onNavigate: (tab: string) => void;
  onCountChange: (count: number) => void;
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);

  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
  return `${Math.floor(seconds / 86400)}d ago`;
}

function typeIcon(type: string) {
  switch (type) {
    case "goal_stalled":
      return <Target size={14} className="text-amber-400" />;
    case "application_reminder":
      return <ClipboardList size={14} className="text-blue-400" />;
    default:
      return <Bell size={14} className="text-zinc-400" />;
  }
}

export default function NotificationPanel({
  onClose,
  onNavigate,
  onCountChange,
}: NotificationPanelProps) {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    apiFetch("/api/notifications")
      .then((r) => r.json())
      .then((data) => setNotifications(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  async function handleClick(n: Notification) {
    if (!n.read) {
      await apiFetch(`/api/notifications/${n.id}/read`, { method: "PATCH" }).catch(() => {});
      setNotifications((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, read: 1 } : x))
      );
      onCountChange(-1);
    }

    // Navigate based on type
    if (n.type === "goal_stalled") {
      onNavigate("goals");
    } else if (n.type === "application_reminder") {
      onNavigate("tracker");
    }
    onClose();
  }

  async function handleMarkAllRead() {
    await apiFetch("/api/notifications/read-all", { method: "POST" }).catch(() => {});
    setNotifications((prev) => prev.map((n) => ({ ...n, read: 1 })));
    onCountChange(0);
  }

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <div className="absolute left-60 top-0 z-50 w-80 max-h-[80vh] bg-zinc-900 border border-zinc-700 rounded-lg shadow-xl flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <h3 className="text-sm font-semibold text-zinc-200">Notifications</h3>
        <div className="flex items-center gap-2">
          {unreadCount > 0 && (
            <button
              onClick={handleMarkAllRead}
              className="text-xs text-zinc-400 hover:text-zinc-200 flex items-center gap-1"
            >
              <CheckCheck size={12} />
              Mark all read
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
          >
            <X size={14} />
          </button>
        </div>
      </div>

      {/* List */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-6 text-xs text-zinc-600 text-center">Loading...</div>
        ) : notifications.length === 0 ? (
          <div className="px-4 py-6 text-xs text-zinc-600 text-center">
            No notifications yet
          </div>
        ) : (
          notifications.map((n) => (
            <button
              key={n.id}
              onClick={() => handleClick(n)}
              className={`w-full text-left px-4 py-3 border-b border-zinc-800/50 hover:bg-zinc-800/50 ${
                n.read ? "opacity-60" : ""
              }`}
            >
              <div className="flex items-start gap-2.5">
                <div className="mt-0.5 shrink-0">{typeIcon(n.type)}</div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-medium text-zinc-200 truncate">
                      {n.title}
                    </span>
                    <span className="text-[10px] text-zinc-600 shrink-0">
                      {timeAgo(n.created_at)}
                    </span>
                  </div>
                  <p className="text-xs text-zinc-400 mt-0.5 line-clamp-2">
                    {n.message}
                  </p>
                </div>
                {!n.read && (
                  <div className="w-1.5 h-1.5 rounded-full bg-cyan-400 shrink-0 mt-1.5" />
                )}
              </div>
            </button>
          ))
        )}
      </div>
    </div>
  );
}
