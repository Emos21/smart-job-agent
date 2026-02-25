interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

const tabs = [
  { id: "chat", label: "Chat", icon: "💬" },
  { id: "search", label: "Search Jobs", icon: "🔍" },
  { id: "analyze", label: "Analyze", icon: "📊" },
  { id: "tracker", label: "Tracker", icon: "📋" },
];

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-60 bg-slate-900 border-r border-slate-700 flex flex-col h-screen">
      <div className="p-5 border-b border-slate-700">
        <h1 className="text-xl font-bold text-emerald-400 tracking-wide">
          KaziAI
        </h1>
        <p className="text-xs text-slate-400 mt-1">AI Career Platform</p>
      </div>
      <nav className="flex-1 py-4">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`w-full text-left px-5 py-3 text-sm flex items-center gap-3 ${
              activeTab === tab.id
                ? "bg-slate-800 text-emerald-400 border-r-2 border-emerald-400"
                : "text-slate-300 hover:bg-slate-800 hover:text-slate-100"
            }`}
          >
            <span>{tab.icon}</span>
            {tab.label}
          </button>
        ))}
      </nav>
      <div className="p-4 border-t border-slate-700 text-xs text-slate-500">
        Multi-Agent AI Platform
      </div>
    </aside>
  );
}
