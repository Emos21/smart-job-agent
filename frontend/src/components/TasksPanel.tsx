import { useState, useEffect } from "react";
import { Cog, Play, Square, CheckCircle2, XCircle, Clock, Loader2, Trash2 } from "lucide-react";
import { apiFetch } from "../lib/api";
import type { AutonomousTask } from "../types";

const STATUS_CONFIG: Record<string, { icon: typeof Clock; color: string; label: string }> = {
  pending: { icon: Clock, color: "text-zinc-500", label: "Pending" },
  running: { icon: Loader2, color: "text-cyan-400", label: "Running" },
  completed: { icon: CheckCircle2, color: "text-emerald-400", label: "Completed" },
  failed: { icon: XCircle, color: "text-red-400", label: "Failed" },
  cancelled: { icon: Square, color: "text-zinc-500", label: "Cancelled" },
};

const TASK_TYPES: { value: string; label: string; description: string }[] = [
  { value: "job_monitor", label: "Job Monitor", description: "Scan for new jobs matching your profile" },
  { value: "app_tracker", label: "Application Tracker", description: "Check status of your applications" },
  { value: "company_deep_dive", label: "Company Research", description: "Deep dive research on a company" },
];

export default function TasksPanel() {
  const [tasks, setTasks] = useState<AutonomousTask[]>([]);
  const [launching, setLaunching] = useState(false);
  const [selectedType, setSelectedType] = useState("job_monitor");
  const [companyName, setCompanyName] = useState("");

  useEffect(() => {
    fetchTasks();
  }, []);

  async function fetchTasks() {
    try {
      const res = await apiFetch("/api/tasks");
      setTasks(await res.json());
    } catch {
      // ignore
    }
  }

  async function handleLaunch() {
    if (launching) return;
    setLaunching(true);
    try {
      const config: Record<string, string> = {};
      if (selectedType === "company_deep_dive") {
        if (!companyName.trim()) return;
        config.company_name = companyName.trim();
      }
      await apiFetch("/api/tasks", {
        method: "POST",
        body: JSON.stringify({ task_type: selectedType, config }),
      });
      setCompanyName("");
      await fetchTasks();
    } catch {
      // ignore
    } finally {
      setLaunching(false);
    }
  }

  async function handleCancel(taskId: number) {
    try {
      await apiFetch(`/api/tasks/${taskId}`, { method: "DELETE" });
      await fetchTasks();
    } catch {
      // ignore
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Background Tasks</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Launch and monitor autonomous background tasks.
          </p>
        </div>

        {/* Launch task */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 space-y-3">
          <div className="flex gap-3">
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2.5 text-sm text-zinc-100 outline-none focus:border-zinc-600"
            >
              {TASK_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label} — {t.description}
                </option>
              ))}
            </select>
            <button
              onClick={handleLaunch}
              disabled={launching || (selectedType === "company_deep_dive" && !companyName.trim())}
              className="flex items-center gap-2 px-4 py-2.5 bg-indigo-600 text-white text-sm rounded-lg disabled:opacity-30 hover:bg-indigo-500"
            >
              {launching ? <Loader2 size={14} /> : <Play size={14} />}
              Launch
            </button>
          </div>
          {selectedType === "company_deep_dive" && (
            <input
              type="text"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              placeholder="Company name to research..."
              className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-zinc-600"
            />
          )}
        </div>

        {/* Task list */}
        {tasks.length === 0 ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <Cog size={24} className="text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">No tasks yet</p>
            <p className="text-xs text-zinc-600 mt-1">
              Launch a task above to get started.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {tasks.map((task) => {
              const statusInfo = STATUS_CONFIG[task.status] || STATUS_CONFIG.pending;
              const Icon = statusInfo.icon;
              return (
                <div
                  key={task.id}
                  className="bg-zinc-900 border border-zinc-800 rounded-xl p-4"
                >
                  <div className="flex items-center gap-3">
                    <Icon size={16} className={`${statusInfo.color} shrink-0`} />
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-zinc-200">
                        {TASK_TYPES.find((t) => t.value === task.task_type)?.label || task.task_type}
                      </p>
                      <div className="flex items-center gap-3 mt-0.5">
                        <span className={`text-xs ${statusInfo.color}`}>
                          {statusInfo.label}
                        </span>
                        <span className="text-xs text-zinc-600">
                          {new Date(task.created_at).toLocaleString()}
                        </span>
                      </div>
                    </div>
                    {task.status === "running" && (
                      <button
                        onClick={() => handleCancel(task.id)}
                        className="p-1.5 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-800"
                        title="Cancel task"
                      >
                        <Trash2 size={14} />
                      </button>
                    )}
                  </div>
                  {task.result_summary && task.status === "completed" && (
                    <details className="mt-2">
                      <summary className="text-xs text-cyan-400 cursor-pointer">
                        View results
                      </summary>
                      <pre className="mt-1 text-xs text-zinc-400 whitespace-pre-wrap max-h-40 overflow-y-auto bg-zinc-800/50 p-2 rounded">
                        {task.result_summary}
                      </pre>
                    </details>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
