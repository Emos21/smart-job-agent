import { useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import SearchPanel from "./components/SearchPanel";
import AnalyzePanel from "./components/AnalyzePanel";
import TrackerPanel from "./components/TrackerPanel";

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [chatKey, setChatKey] = useState(0);

  async function handleNewChat() {
    // Clear backend history first, then remount ChatPanel with fresh state
    await fetch("/api/chat/history", { method: "DELETE" }).catch(() => {});
    setActiveTab("chat");
    setChatKey((k) => k + 1);
  }

  return (
    <div className="flex h-screen bg-zinc-950">
      <Sidebar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        open={sidebarOpen}
        onToggle={() => setSidebarOpen((o) => !o)}
        onNewChat={handleNewChat}
      />
      <main className="flex-1 overflow-hidden">
        {activeTab === "chat" && <ChatPanel key={chatKey} fresh={chatKey > 0} />}
        {activeTab === "search" && <SearchPanel />}
        {activeTab === "analyze" && <AnalyzePanel />}
        {activeTab === "tracker" && <TrackerPanel />}
      </main>
    </div>
  );
}
