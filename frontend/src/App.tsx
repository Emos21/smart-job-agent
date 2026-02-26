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
import AuthPage from "./components/AuthPage";
import type { Conversation, User } from "./types";
import { apiFetch, getToken, clearToken, setOnUnauthorized } from "./lib/api";

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

  // Poll for unread notification count every 30s when logged in
  useEffect(() => {
    if (!user) return;

    function fetchCount() {
      apiFetch("/api/notifications/count")
        .then((r) => r.json())
        .then((data) => setUnreadCount(data.count))
        .catch(() => {});
    }

    fetchCount();
    const interval = setInterval(fetchCount, 30000);
    return () => clearInterval(interval);
  }, [user]);

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
        {activeTab === "profile" && <ProfilePanel />}
      </main>
    </div>
  );
}
