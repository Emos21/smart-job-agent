import { useState, useEffect } from "react";
import { Briefcase, FileText, MessageSquare, ClipboardList, User, Lightbulb, ArrowRight } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { Suggestion } from "../types";

interface DashboardData {
  total_jobs_saved: number;
  total_applications: number;
  total_conversations: number;
  total_resumes: number;
  has_profile: boolean;
  application_status: Record<string, number>;
  recent_applications: {
    title: string;
    company: string;
    status: string;
    updated_at: string;
  }[];
}

interface DashboardPanelProps {
  onNavigate?: (tab: string, chatPrompt?: string) => void;
}

const STATUS_COLORS: Record<string, string> = {
  saved: "bg-zinc-600",
  applied: "bg-blue-500",
  interviewing: "bg-yellow-500",
  offered: "bg-green-500",
  rejected: "bg-red-500",
};

export default function DashboardPanel({ onNavigate }: DashboardPanelProps = {}) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);

  useEffect(() => {
    apiFetch("/api/dashboard")
      .then((r) => r.json())
      .then(setData)
      .catch(() => {});
    apiFetch("/api/suggestions")
      .then((r) => r.json())
      .then(setSuggestions)
      .catch(() => {});
  }, []);

  if (!data) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
        Loading dashboard...
      </div>
    );
  }

  const stats = [
    { label: "Jobs Saved", value: data.total_jobs_saved, icon: Briefcase, color: "text-blue-400" },
    { label: "Applications", value: data.total_applications, icon: ClipboardList, color: "text-indigo-400" },
    { label: "Conversations", value: data.total_conversations, icon: MessageSquare, color: "text-cyan-400" },
    { label: "Resumes", value: data.total_resumes, icon: FileText, color: "text-emerald-400" },
  ];

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Dashboard</h2>
          <p className="text-sm text-zinc-500 mt-1">Your job search at a glance.</p>
        </div>

        {/* Stat cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((s) => {
            const Icon = s.icon;
            return (
              <div
                key={s.label}
                className="bg-zinc-900 border border-zinc-800 rounded-xl p-4"
              >
                <div className="flex items-center gap-2 mb-2">
                  <Icon size={16} className={s.color} />
                  <span className="text-xs text-zinc-500">{s.label}</span>
                </div>
                <p className="text-2xl font-semibold text-zinc-100">{s.value}</p>
              </div>
            );
          })}
        </div>

        {/* Suggestions */}
        {suggestions.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
              <Lightbulb size={14} className="text-cyan-400" />
              Suggestions
            </h3>
            {suggestions.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  if (onNavigate) {
                    if (s.action.startsWith("chat:")) {
                      onNavigate("chat", s.action.slice(5));
                    } else {
                      onNavigate(s.action);
                    }
                  }
                }}
                className="w-full flex items-center gap-3 p-3 bg-cyan-500/5 border border-cyan-500/20 rounded-xl text-left hover:bg-cyan-500/10"
              >
                <div className="flex-1">
                  <p className="text-sm text-zinc-200">{s.message}</p>
                </div>
                <ArrowRight size={14} className="text-cyan-400 shrink-0" />
              </button>
            ))}
          </div>
        )}

        {/* Profile status */}
        {!data.has_profile && (
          <div className="bg-indigo-600/10 border border-indigo-500/20 rounded-xl p-4 flex items-center gap-3">
            <User size={18} className="text-indigo-400 shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-zinc-200">Complete your profile</p>
              <p className="text-xs text-zinc-400 mt-0.5">
                Set your target role, skills, and upload a resume so Kazi can give personalized advice.
              </p>
            </div>
          </div>
        )}

        {/* Application funnel */}
        {Object.keys(data.application_status).length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-base font-medium text-zinc-100 mb-4">Application Pipeline</h3>
            <div className="flex gap-3 flex-wrap">
              {Object.entries(data.application_status).map(([status, count]) => (
                <div key={status} className="flex items-center gap-2">
                  <span className={`w-2.5 h-2.5 rounded-full ${STATUS_COLORS[status] || "bg-zinc-500"}`} />
                  <span className="text-sm text-zinc-300 capitalize">{status}</span>
                  <span className="text-sm font-medium text-zinc-100">{count}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent applications */}
        {data.recent_applications.length > 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6">
            <h3 className="text-base font-medium text-zinc-100 mb-4">Recent Applications</h3>
            <div className="space-y-3">
              {data.recent_applications.map((app, i) => (
                <div
                  key={i}
                  className="flex items-center gap-3 p-3 bg-zinc-800/50 rounded-lg"
                >
                  <span className={`w-2 h-2 rounded-full shrink-0 ${STATUS_COLORS[app.status] || "bg-zinc-500"}`} />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{app.title}</p>
                    <p className="text-xs text-zinc-500">{app.company}</p>
                  </div>
                  <span className="text-xs text-zinc-500 capitalize shrink-0">{app.status}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {data.total_jobs_saved === 0 && data.total_applications === 0 && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <Briefcase size={24} className="text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">No activity yet</p>
            <p className="text-xs text-zinc-600 mt-1">
              Start a chat to search for jobs or analyze your resume.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
