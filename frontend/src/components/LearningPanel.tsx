import { useState } from "react";
import { BookOpen, Clock, Target, ChevronDown, ChevronRight } from "lucide-react";
import { apiFetch } from "../lib/api";

interface LearningPath {
  priority: number;
  skill: string;
  starting_level: string;
  estimated_hours: number;
  estimated_weeks: number;
  resources: string[];
  milestones: string[];
}

interface LearningData {
  success: boolean;
  message?: string;
  target_role?: string;
  total_skills_to_learn?: number;
  total_estimated_hours?: number;
  total_estimated_weeks?: number;
  learning_paths?: LearningPath[];
}

export default function LearningPanel() {
  const [data, setData] = useState<LearningData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  async function generate() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/learning-path", { method: "POST" });
      if (!res.ok) {
        const err = await res.json();
        setError(err.detail || "Failed to generate learning path");
        return;
      }
      setData(await res.json());
    } catch {
      setError("Something went wrong. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function toggleExpand(priority: number) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(priority)) next.delete(priority);
      else next.add(priority);
      return next;
    });
  }

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold text-zinc-100">Learning Path</h2>
            <p className="text-sm text-zinc-500 mt-1">
              Personalized study plan based on your profile and target role.
            </p>
          </div>
          <button
            onClick={generate}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-50"
          >
            <BookOpen size={14} />
            {loading ? "Generating..." : data ? "Regenerate" : "Generate"}
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-sm text-red-300">
            {error}
          </div>
        )}

        {data?.message && !data.learning_paths?.length && (
          <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-6 text-center">
            <Target size={24} className="text-emerald-400 mx-auto mb-2" />
            <p className="text-sm text-emerald-300">{data.message}</p>
          </div>
        )}

        {data?.learning_paths && data.learning_paths.length > 0 && (
          <>
            {/* Summary bar */}
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 flex items-center gap-6">
              {data.target_role && (
                <div>
                  <p className="text-xs text-zinc-500">Target</p>
                  <p className="text-sm text-zinc-200">{data.target_role}</p>
                </div>
              )}
              <div>
                <p className="text-xs text-zinc-500">Skills to learn</p>
                <p className="text-sm text-zinc-200">{data.total_skills_to_learn}</p>
              </div>
              <div>
                <p className="text-xs text-zinc-500">Estimated time</p>
                <p className="text-sm text-zinc-200">
                  {data.total_estimated_hours}h ({data.total_estimated_weeks} weeks)
                </p>
              </div>
            </div>

            {/* Skill cards */}
            <div className="space-y-3">
              {data.learning_paths.map((path) => {
                const isOpen = expanded.has(path.priority);
                return (
                  <div
                    key={path.priority}
                    className="bg-zinc-900 border border-zinc-800 rounded-xl overflow-hidden"
                  >
                    <button
                      onClick={() => toggleExpand(path.priority)}
                      className="w-full flex items-center gap-3 p-4 text-left hover:bg-zinc-800/50"
                    >
                      <span className="w-6 h-6 rounded-full bg-indigo-600/20 text-indigo-400 flex items-center justify-center text-xs font-medium shrink-0">
                        {path.priority}
                      </span>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-zinc-100">{path.skill}</p>
                        <p className="text-xs text-zinc-500">
                          {path.starting_level} · {path.estimated_hours}h · {path.estimated_weeks} weeks
                        </p>
                      </div>
                      <Clock size={14} className="text-zinc-600 shrink-0" />
                      {isOpen ? (
                        <ChevronDown size={16} className="text-zinc-500 shrink-0" />
                      ) : (
                        <ChevronRight size={16} className="text-zinc-500 shrink-0" />
                      )}
                    </button>
                    {isOpen && (
                      <div className="px-4 pb-4 space-y-3 border-t border-zinc-800 pt-3">
                        <div>
                          <p className="text-xs font-medium text-zinc-400 mb-1.5">Resources</p>
                          <ul className="space-y-1">
                            {path.resources.map((r, i) => (
                              <li key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                                <span className="text-indigo-400 mt-0.5">-</span>
                                {r}
                              </li>
                            ))}
                          </ul>
                        </div>
                        <div>
                          <p className="text-xs font-medium text-zinc-400 mb-1.5">Milestones</p>
                          <ul className="space-y-1">
                            {path.milestones.map((m, i) => (
                              <li key={i} className="text-sm text-zinc-300 flex items-start gap-2">
                                <span className="text-cyan-400 mt-0.5">-</span>
                                {m}
                              </li>
                            ))}
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </>
        )}

        {!data && !loading && !error && (
          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-8 text-center">
            <BookOpen size={24} className="text-zinc-600 mx-auto mb-3" />
            <p className="text-sm text-zinc-400">
              Click Generate to create a personalized learning path
            </p>
            <p className="text-xs text-zinc-600 mt-1">
              Make sure your profile has your current skills and target role set.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
