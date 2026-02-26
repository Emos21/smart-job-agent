import { useState, useEffect } from "react";
import { Target, ChevronDown, ChevronRight, Play, CheckCircle2, Clock, XCircle, Loader2, Square, Zap, Lightbulb, Check, X } from "lucide-react";
import { apiFetch, getToken } from "../lib/api";
import type { Goal, GoalStep } from "../types";

interface GoalWithProgress extends Goal {
  total_steps: number;
  completed_steps: number;
  progress: number;
}

interface GoalDetail extends GoalWithProgress {
  steps: GoalStep[];
}

interface AutoExecStatus {
  goalId: number;
  currentStep: number;
  messages: string[];
}

const STEP_STATUS_ICONS: Record<string, { icon: typeof Clock; color: string }> = {
  pending: { icon: Clock, color: "text-zinc-500" },
  in_progress: { icon: Loader2, color: "text-cyan-400" },
  completed: { icon: CheckCircle2, color: "text-emerald-400" },
  skipped: { icon: Clock, color: "text-zinc-600" },
  failed: { icon: XCircle, color: "text-red-400" },
};

interface SuggestedGoal {
  id: number;
  title: string;
  description: string;
  origin: string;
  trigger_type: string;
}

export default function GoalsPanel() {
  const [goals, setGoals] = useState<GoalWithProgress[]>([]);
  const [suggestedGoals, setSuggestedGoals] = useState<SuggestedGoal[]>([]);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [goalDetail, setGoalDetail] = useState<GoalDetail | null>(null);
  const [goalInput, setGoalInput] = useState("");
  const [creating, setCreating] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [autoExecuting, setAutoExecuting] = useState<number | null>(null);
  const [autoExecStatus, setAutoExecStatus] = useState<AutoExecStatus | null>(null);

  useEffect(() => {
    fetchGoals();
    fetchSuggested();
  }, []);

  async function fetchGoals() {
    try {
      const res = await apiFetch("/api/goals");
      const data = await res.json();
      setGoals(data);
    } catch {
      // ignore
    }
  }

  async function fetchSuggested() {
    try {
      const res = await apiFetch("/api/goals/suggested");
      setSuggestedGoals(await res.json());
    } catch {
      // ignore
    }
  }

  async function handleApprove(goalId: number) {
    try {
      await apiFetch(`/api/goals/${goalId}/approve`, { method: "POST" });
      setSuggestedGoals((prev) => prev.filter((g) => g.id !== goalId));
      await fetchGoals();
    } catch {
      // ignore
    }
  }

  async function handleDismiss(goalId: number) {
    try {
      await apiFetch(`/api/goals/${goalId}/dismiss`, { method: "POST" });
      setSuggestedGoals((prev) => prev.filter((g) => g.id !== goalId));
    } catch {
      // ignore
    }
  }

  async function handleCreate() {
    if (!goalInput.trim() || creating) return;
    setCreating(true);
    try {
      await apiFetch("/api/goals", {
        method: "POST",
        body: JSON.stringify({ goal_text: goalInput.trim() }),
      });
      setGoalInput("");
      await fetchGoals();
    } catch {
      // ignore
    } finally {
      setCreating(false);
    }
  }

  async function toggleExpand(goalId: number) {
    if (expandedId === goalId) {
      setExpandedId(null);
      setGoalDetail(null);
      return;
    }
    setExpandedId(goalId);
    try {
      const res = await apiFetch(`/api/goals/${goalId}`);
      const data = await res.json();
      setGoalDetail(data);
    } catch {
      // ignore
    }
  }

  async function handleExecuteNext(goalId: number) {
    if (executing) return;
    setExecuting(true);
    try {
      await apiFetch(`/api/goals/${goalId}/execute-next`, { method: "POST" });
      // Refresh detail
      const res = await apiFetch(`/api/goals/${goalId}`);
      const data = await res.json();
      setGoalDetail(data);
      await fetchGoals();
    } catch {
      // ignore
    } finally {
      setExecuting(false);
    }
  }

  async function handleAutoExecute(goalId: number) {
    if (autoExecuting) return;
    setAutoExecuting(goalId);
    setAutoExecStatus({ goalId, currentStep: 0, messages: [] });

    try {
      const token = getToken();
      const headers: Record<string, string> = { "Content-Type": "application/json" };
      if (token) headers["Authorization"] = `Bearer ${token}`;

      const res = await fetch(`/api/goals/${goalId}/auto-execute`, {
        method: "POST",
        headers,
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No reader");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          try {
            const event = JSON.parse(line.slice(6));

            if (event.type === "goal_step_start") {
              setAutoExecStatus((prev) => prev ? {
                ...prev,
                currentStep: event.step_number,
                messages: [...prev.messages, `Running: ${event.title} (${event.agent})`],
              } : null);
            } else if (event.type === "goal_step_complete") {
              setAutoExecStatus((prev) => prev ? {
                ...prev,
                messages: [...prev.messages, `Step ${event.step_number} ${event.status}`],
              } : null);
            } else if (event.type === "goal_replan") {
              setAutoExecStatus((prev) => prev ? {
                ...prev,
                messages: [...prev.messages, `Plan adjusted: ${event.reason}`],
              } : null);
            }
          } catch {
            // skip malformed
          }
        }
      }
    } catch {
      // ignore
    } finally {
      setAutoExecuting(null);
      setAutoExecStatus(null);
      // Refresh goal detail and list
      try {
        const res = await apiFetch(`/api/goals/${goalId}`);
        const data = await res.json();
        setGoalDetail(data);
        await fetchGoals();
      } catch {
        // ignore
      }
    }
  }

  async function handleCancelAutoExecute(goalId: number) {
    try {
      await apiFetch(`/api/goals/${goalId}/cancel`, { method: "POST" });
    } catch {
      // ignore
    }
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-3xl mx-auto px-6 py-8 space-y-8">
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Goals</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Set career goals and track multi-step AI plans.
          </p>
        </div>

        {/* Create goal */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={goalInput}
              onChange={(e) => setGoalInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreate()}
              placeholder='e.g. "Help me land a backend role at Stripe"'
              className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-4 py-2.5 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-zinc-600"
            />
            <button
              onClick={handleCreate}
              disabled={!goalInput.trim() || creating}
              className="px-4 py-2.5 bg-indigo-600 text-white text-sm rounded-lg disabled:opacity-30 hover:bg-indigo-500"
            >
              {creating ? "Planning..." : "Create Plan"}
            </button>
          </div>
        </div>

        {/* Suggested for You */}
        {suggestedGoals.length > 0 && (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-zinc-400 flex items-center gap-2">
              <Lightbulb size={14} className="text-amber-400" />
              Suggested for You
            </h3>
            {suggestedGoals.map((sg) => (
              <div
                key={sg.id}
                className="bg-amber-500/5 border border-amber-500/20 rounded-xl p-4"
              >
                <div className="flex items-start gap-3">
                  <Lightbulb size={16} className="text-amber-400 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200">{sg.title}</p>
                    <p className="text-xs text-zinc-500 mt-0.5">{sg.description}</p>
                    {sg.trigger_type && (
                      <span className="inline-block mt-1 text-[10px] text-amber-400/80 bg-amber-500/10 px-2 py-0.5 rounded-full">
                        {sg.trigger_type.replace(/_/g, " ")}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button
                      onClick={() => handleApprove(sg.id)}
                      className="p-1.5 rounded text-emerald-400 hover:bg-emerald-500/10"
                      title="Approve"
                    >
                      <Check size={16} />
                    </button>
                    <button
                      onClick={() => handleDismiss(sg.id)}
                      className="p-1.5 rounded text-zinc-500 hover:text-red-400 hover:bg-red-500/10"
                      title="Dismiss"
                    >
                      <X size={16} />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Goal list */}
        {goals.length === 0 ? (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <Target size={24} className="text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">No goals yet</p>
            <p className="text-xs text-zinc-600 mt-1">
              Create a goal above and AI will plan the steps.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {goals.map((goal) => (
              <div
                key={goal.id}
                className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden"
              >
                {/* Goal header */}
                <button
                  onClick={() => toggleExpand(goal.id)}
                  className="w-full flex items-center gap-3 p-4 text-left hover:bg-zinc-800/50"
                >
                  {expandedId === goal.id ? (
                    <ChevronDown size={16} className="text-zinc-500 shrink-0" />
                  ) : (
                    <ChevronRight size={16} className="text-zinc-500 shrink-0" />
                  )}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{goal.title}</p>
                    <div className="flex items-center gap-3 mt-1">
                      <span className={`text-xs capitalize ${
                        goal.status === "active" ? "text-cyan-400" :
                        goal.status === "completed" ? "text-emerald-400" :
                        goal.status === "paused" ? "text-yellow-400" :
                        "text-zinc-500"
                      }`}>
                        {goal.status}
                      </span>
                      <span className="text-xs text-zinc-500">
                        {goal.completed_steps}/{goal.total_steps} steps
                      </span>
                    </div>
                  </div>
                  {/* Progress bar */}
                  <div className="w-24 h-1.5 bg-zinc-800 rounded-full overflow-hidden shrink-0">
                    <div
                      className="h-full bg-indigo-500 rounded-full"
                      style={{ width: `${Math.round(goal.progress * 100)}%` }}
                    />
                  </div>
                </button>

                {/* Expanded steps */}
                {expandedId === goal.id && goalDetail && (
                  <div className="border-t border-zinc-800 p-4 space-y-2">
                    {goalDetail.steps.map((step) => {
                      const statusInfo = STEP_STATUS_ICONS[step.status] || STEP_STATUS_ICONS.pending;
                      const Icon = statusInfo.icon;
                      return (
                        <div
                          key={step.id}
                          className="flex items-start gap-3 p-3 bg-zinc-800/30 rounded-lg"
                        >
                          <Icon size={14} className={`${statusInfo.color} shrink-0 mt-0.5`} />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm text-zinc-200">{step.title}</p>
                            <p className="text-xs text-zinc-500 mt-0.5">
                              {step.agent_name && (
                                <span className="text-zinc-400 capitalize">{step.agent_name} Agent</span>
                              )}
                              {step.description && ` — ${step.description}`}
                            </p>
                            {step.output && step.status === "completed" && (
                              <details className="mt-2">
                                <summary className="text-xs text-cyan-400 cursor-pointer">
                                  View output
                                </summary>
                                <pre className="mt-1 text-xs text-zinc-400 whitespace-pre-wrap max-h-40 overflow-y-auto bg-zinc-900 p-2 rounded">
                                  {step.output}
                                </pre>
                              </details>
                            )}
                          </div>
                          <span className={`text-xs capitalize shrink-0 ${statusInfo.color}`}>
                            {step.status}
                          </span>
                        </div>
                      );
                    })}

                    {/* Auto-execution status */}
                    {autoExecuting === goal.id && autoExecStatus && (
                      <div className="mt-2 space-y-1">
                        {autoExecStatus.messages.slice(-4).map((msg, i) => (
                          <div key={i} className="text-xs text-cyan-400/80 bg-cyan-500/5 border border-cyan-500/10 rounded px-2 py-1">
                            {msg}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Action buttons */}
                    {goal.status === "active" && goalDetail.steps.some((s) => s.status === "pending") && (
                      <div className="flex items-center gap-2 mt-2">
                        {autoExecuting === goal.id ? (
                          <button
                            onClick={() => handleCancelAutoExecute(goal.id)}
                            className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white text-sm rounded-lg hover:bg-red-500"
                          >
                            <Square size={14} />
                            Stop
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={() => handleExecuteNext(goal.id)}
                              disabled={executing || autoExecuting !== null}
                              className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg disabled:opacity-30 hover:bg-indigo-500"
                            >
                              {executing ? <Loader2 size={14} /> : <Play size={14} />}
                              {executing ? "Running..." : "Execute Next Step"}
                            </button>
                            <button
                              onClick={() => handleAutoExecute(goal.id)}
                              disabled={executing || autoExecuting !== null}
                              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white text-sm rounded-lg disabled:opacity-30 hover:bg-cyan-500"
                            >
                              <Zap size={14} />
                              Auto-Execute All
                            </button>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
