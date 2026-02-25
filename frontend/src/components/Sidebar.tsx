import {
  MessageSquare,
  Search,
  BarChart3,
  ClipboardList,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  open: boolean;
  onToggle: () => void;
  onNewChat: () => void;
}

const tabs = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "search", label: "Search Jobs", icon: Search },
  { id: "analyze", label: "Analyze", icon: BarChart3 },
  { id: "tracker", label: "Tracker", icon: ClipboardList },
];

export default function Sidebar({
  activeTab,
  onTabChange,
  open,
  onToggle,
  onNewChat,
}: SidebarProps) {
  return (
    <aside
      className={`${
        open ? "w-60" : "w-16"
      } bg-zinc-900 border-r border-zinc-800 flex flex-col h-screen`}
    >
      {/* Header */}
      <div className="p-3 border-b border-zinc-800 flex items-center justify-between gap-2">
        {open && (
          <h1 className="text-lg font-semibold text-teal-400 tracking-wide pl-1">
            KaziAI
          </h1>
        )}
        <button
          onClick={onToggle}
          className="p-2 rounded-lg text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
          title={open ? "Collapse sidebar" : "Expand sidebar"}
        >
          {open ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
        </button>
      </div>

      {/* New Chat */}
      <div className="px-3 pt-3">
        <button
          onClick={onNewChat}
          className={`w-full flex items-center gap-2 rounded-lg border border-zinc-700 text-sm text-zinc-200 hover:bg-zinc-800 ${
            open ? "px-3 py-2.5 justify-start" : "p-2.5 justify-center"
          }`}
        >
          <Plus size={16} />
          {open && <span>New Chat</span>}
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 py-3 space-y-0.5 px-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const active = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`w-full flex items-center gap-3 rounded-lg text-sm ${
                open ? "px-3 py-2.5" : "px-0 py-2.5 justify-center"
              } ${
                active
                  ? "bg-zinc-800 text-teal-400"
                  : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
              }`}
              title={!open ? tab.label : undefined}
            >
              <Icon size={18} />
              {open && <span>{tab.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div
        className={`p-3 border-t border-zinc-800 text-xs text-zinc-600 ${
          open ? "" : "text-center"
        }`}
      >
        {open ? "Multi-Agent AI Platform" : "AI"}
      </div>
    </aside>
  );
}
