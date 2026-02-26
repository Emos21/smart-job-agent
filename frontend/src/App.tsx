import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import SearchPanel from "./components/SearchPanel";
import AnalyzePanel from "./components/AnalyzePanel";
import TrackerPanel from "./components/TrackerPanel";
import ProfilePanel from "./components/ProfilePanel";
import DashboardPanel from "./components/DashboardPanel";
import LearningPanel from "./components/LearningPanel";
import GoalsPanel from "./components/GoalsPanel";
import NotificationPanel from "./components/NotificationPanel";
import TasksPanel from "./components/TasksPanel";
import AuthPage from "./components/AuthPage";
import type { Conversation, User } from "./types";
import { apiFetch, getToken, clearToken, setOnUnauthorized } from "./lib/api";
import { useWebSocket } from "./hooks/useWebSocket";

export default function App() {
  const [user, setUser] = useState<User | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatKey, setChatKey] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const [showNotifications, setShowNotifications] = useState(false);

  // Handle 401 from any API call
  useEffect(() => {
    setOnUnauthorized(() => {
      setUser(null);
      setConversations([]);
      setActiveConversationId(null);
    });
  }, []);

  // Verify token on mount
  useEffect(() => {
    const token = getToken();
    if (!token) {
      setAuthChecked(true);
      return;
    }
    apiFetch("/api/auth/me")
      .then((res) => {
        if (res.ok) return res.json();
        throw new Error("Invalid token");
      })
      .then((data) => setUser(data))
      .catch(() => clearToken())
      .finally(() => setAuthChecked(true));
  }, []);

  const fetchConversations = useCallback(async () => {
    if (!user) return;
    try {
      const res = await apiFetch("/api/conversations");
      const data = await res.json();
      setConversations(data);
    } catch {
      // ignore
    }
  }, [user]);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

  // WebSocket for real-time push (replaces 30s polling)
  const { lastMessage, isConnected } = useWebSocket(user ? getToken() : null);

  // Handle incoming WebSocket messages
  useEffect(() => {
    if (!lastMessage || typeof lastMessage !== "object") return;
    const msg = lastMessage as Record<string, unknown>;

    if (msg.type === "notification") {
      setUnreadCount((c) => c + 1);
    } else if (msg.type === "task_update") {
      // Task state updates handled by TasksPanel
    }
  }, [lastMessage]);

  // Fetch initial unread count on login (one-time, not polling)
  useEffect(() => {
    if (!user) return;
    apiFetch("/api/notifications/count")
      .then((r) => r.json())
      .then((data) => setUnreadCount(data.count))
      .catch(() => {});
  }, [user]);

  // Fallback: poll every 60s only if WebSocket is disconnected
  useEffect(() => {
    if (!user || isConnected) return;

    const interval = setInterval(() => {
      apiFetch("/api/notifications/count")
        .then((r) => r.json())
        .then((data) => setUnreadCount(data.count))
        .catch(() => {});
    }, 60000);
    return () => clearInterval(interval);
  }, [user, isConnected]);

  function handleNewChat() {
    setActiveConversationId(null);
    setActiveTab("chat");
    setChatKey((k) => k + 1);
  }

  function handleSelectConversation(id: number) {
    setActiveConversationId(id);
    setActiveTab("chat");
    setChatKey((k) => k + 1);
  }

  async function handleDeleteConversation(id: number) {
    await apiFetch(`/api/conversations/${id}`, { method: "DELETE" }).catch(() => {});
    setConversations((prev) => prev.filter((c) => c.id !== id));
    if (activeConversationId === id) {
      setActiveConversationId(null);
      setChatKey((k) => k + 1);
    }
  }

  function handleConversationCreated(id: number) {
    setActiveConversationId(id);
    fetchConversations();
  }

  function handleLogout() {
    clearToken();
    setUser(null);
    setConversations([]);
    setActiveConversationId(null);
  }

  // Loading state while checking auth
  if (!authChecked) {
    return (
      <div className="flex h-screen bg-zinc-950 items-center justify-center">
        <div className="text-zinc-500 text-sm">Loading...</div>
      </div>
    );
  }

  // Not logged in
  if (!user) {
    return <AuthPage onAuth={setUser} />;
  }

  return (
    <div className="flex h-screen bg-zinc-950">
      <div className="relative">
        <Sidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          open={sidebarOpen}
          onToggle={() => setSidebarOpen((o) => !o)}
          onNewChat={handleNewChat}
          conversations={conversations}
          activeConversationId={activeConversationId}
          onSelectConversation={handleSelectConversation}
          onDeleteConversation={handleDeleteConversation}
          user={user}
          onLogout={handleLogout}
          unreadCount={unreadCount}
          onNotificationsClick={() => setShowNotifications((s) => !s)}
        />
        {showNotifications && (
          <NotificationPanel
            onClose={() => setShowNotifications(false)}
            onNavigate={(tab) => {
              setActiveTab(tab);
              setShowNotifications(false);
            }}
            onCountChange={(delta) => {
              if (delta === 0) {
                setUnreadCount(0);
              } else {
                setUnreadCount((c) => Math.max(0, c + delta));
              }
            }}
          />
        )}
      </div>
      <main className="flex-1 overflow-hidden">
        {activeTab === "chat" && (
          <ChatPanel
            key={chatKey}
            conversationId={activeConversationId}
            onConversationCreated={handleConversationCreated}
          />
        )}
        {activeTab === "dashboard" && <DashboardPanel />}
        {activeTab === "goals" && <GoalsPanel />}
        {activeTab === "search" && <SearchPanel />}
        {activeTab === "analyze" && <AnalyzePanel />}
        {activeTab === "tracker" && <TrackerPanel />}
        {activeTab === "learn" && <LearningPanel />}
        {activeTab === "tasks" && <TasksPanel />}
        {activeTab === "profile" && <ProfilePanel />}
      </main>
    </div>
  );
}
