import {
  MessageSquare,
  Search,
  BarChart3,
  ClipboardList,
  Plus,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
  LogOut,
} from "lucide-react";
import { useState } from "react";
import type { Conversation, User } from "../types";

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  open: boolean;
  onToggle: () => void;
  onNewChat: () => void;
  conversations: Conversation[];
  activeConversationId: number | null;
  onSelectConversation: (id: number) => void;
  onDeleteConversation: (id: number) => void;
  user: User;
  onLogout: () => void;
}

const tabs = [
  { id: "chat", label: "Chat", icon: MessageSquare },
  { id: "search", label: "Search Jobs", icon: Search },
  { id: "analyze", label: "Analyze", icon: BarChart3 },
  { id: "tracker", label: "Tracker", icon: ClipboardList },
];

interface DateGroup {
  label: string;
  conversations: Conversation[];
}

function groupByDate(conversations: Conversation[]): DateGroup[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const week = new Date(today.getTime() - 7 * 86400000);

  const groups: Record<string, Conversation[]> = {
    Today: [],
    Yesterday: [],
    "Previous 7 Days": [],
    Older: [],
  };

  for (const conv of conversations) {
    const d = new Date(conv.updated_at);
    if (d >= today) {
      groups["Today"].push(conv);
    } else if (d >= yesterday) {
      groups["Yesterday"].push(conv);
    } else if (d >= week) {
      groups["Previous 7 Days"].push(conv);
    } else {
      groups["Older"].push(conv);
    }
  }

  return ["Today", "Yesterday", "Previous 7 Days", "Older"]
    .filter((label) => groups[label].length > 0)
    .map((label) => ({ label, conversations: groups[label] }));
}

export default function Sidebar({
  activeTab,
  onTabChange,
  open,
  onToggle,
  onNewChat,
  conversations,
  activeConversationId,
  onSelectConversation,
  onDeleteConversation,
  user,
  onLogout,
}: SidebarProps) {
  const [hoveredId, setHoveredId] = useState<number | null>(null);
  const dateGroups = groupByDate(conversations);

  const initials = (user.name || user.email)
    .split(/[\s@]/)
    .filter(Boolean)
    .slice(0, 2)
    .map((s) => s[0].toUpperCase())
    .join("");

  return (
    <aside
      className={`${
        open ? "w-60" : "w-16"
      } bg-zinc-900 border-r border-zinc-800 flex flex-col h-screen`}
    >
      {/* Header */}
      <div className="p-3 border-b border-zinc-800 flex items-center justify-between gap-2">
        {open && (
          <h1 className="text-lg font-semibold text-cyan-400 tracking-wide pl-1">
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

      {/* Nav tabs */}
      <nav className="py-3 space-y-0.5 px-2">
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
                  ? "bg-zinc-800 text-indigo-400"
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

      {/* Conversation list (only when expanded) */}
      {open && (
        <div className="flex-1 overflow-y-auto border-t border-zinc-800 px-2 py-2">
          {dateGroups.map((group) => (
            <div key={group.label} className="mb-2">
              <div className="px-2 py-1.5 text-[11px] font-medium text-zinc-500 uppercase tracking-wider">
                {group.label}
              </div>
              {group.conversations.map((conv) => (
                <button
                  key={conv.id}
                  onClick={() => onSelectConversation(conv.id)}
                  onMouseEnter={() => setHoveredId(conv.id)}
                  onMouseLeave={() => setHoveredId(null)}
                  className={`w-full flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-left group ${
                    activeConversationId === conv.id
                      ? "bg-zinc-800 text-zinc-100"
                      : "text-zinc-400 hover:bg-zinc-800/60 hover:text-zinc-200"
                  }`}
                >
                  <span className="truncate flex-1">{conv.title}</span>
                  {hoveredId === conv.id && (
                    <span
                      role="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteConversation(conv.id);
                      }}
                      className="shrink-0 p-0.5 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-700"
                      title="Delete conversation"
                    >
                      <Trash2 size={14} />
                    </span>
                  )}
                </button>
              ))}
            </div>
          ))}
          {conversations.length === 0 && (
            <div className="px-2 py-4 text-xs text-zinc-600 text-center">
              No conversations yet
            </div>
          )}
        </div>
      )}

      {/* Spacer when collapsed (so footer stays at bottom) */}
      {!open && <div className="flex-1" />}

      {/* User footer */}
      <div className="p-3 border-t border-zinc-800">
        {open ? (
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-indigo-600/20 flex items-center justify-center shrink-0 text-xs font-semibold text-indigo-400">
              {initials}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm text-zinc-200 truncate">
                {user.name || user.email}
              </p>
            </div>
            <button
              onClick={onLogout}
              className="p-1.5 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
              title="Sign out"
            >
              <LogOut size={16} />
            </button>
          </div>
        ) : (
          <button
            onClick={onLogout}
            className="w-full flex justify-center p-2 rounded-lg text-zinc-500 hover:text-zinc-200 hover:bg-zinc-800"
            title="Sign out"
          >
            <LogOut size={16} />
          </button>
        )}
      </div>
    </aside>
  );
}
