import { useState, useEffect, useCallback } from "react";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import SearchPanel from "./components/SearchPanel";
import AnalyzePanel from "./components/AnalyzePanel";
import TrackerPanel from "./components/TrackerPanel";
import type { Conversation } from "./types";

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatKey, setChatKey] = useState(0);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<number | null>(null);

  const fetchConversations = useCallback(async () => {
    try {
      const res = await fetch("/api/conversations");
      const data = await res.json();
      setConversations(data);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchConversations();
  }, [fetchConversations]);

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
    await fetch(`/api/conversations/${id}`, { method: "DELETE" }).catch(() => {});
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

  return (
    <div className="flex h-screen bg-zinc-950">
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
      />
      <main className="flex-1 overflow-hidden">
        {activeTab === "chat" && (
          <ChatPanel
            key={chatKey}
            conversationId={activeConversationId}
            onConversationCreated={handleConversationCreated}
          />
        )}
        {activeTab === "search" && <SearchPanel />}
        {activeTab === "analyze" && <AnalyzePanel />}
        {activeTab === "tracker" && <TrackerPanel />}
      </main>
    </div>
  );
}
