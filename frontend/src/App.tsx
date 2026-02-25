import { useState } from "react";
import Sidebar from "./components/Sidebar";
import ChatPanel from "./components/ChatPanel";
import SearchPanel from "./components/SearchPanel";
import AnalyzePanel from "./components/AnalyzePanel";
import TrackerPanel from "./components/TrackerPanel";

export default function App() {
  const [activeTab, setActiveTab] = useState("chat");

  return (
    <div className="flex h-screen bg-slate-950">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <main className="flex-1 overflow-hidden">
        {activeTab === "chat" && <ChatPanel />}
        {activeTab === "search" && <SearchPanel />}
        {activeTab === "analyze" && <AnalyzePanel />}
        {activeTab === "tracker" && <TrackerPanel />}
      </main>
    </div>
  );
}
