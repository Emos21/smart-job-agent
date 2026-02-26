import { useState, useEffect } from "react";
import { ExternalLink } from "lucide-react";
import PanelHeader from "./PanelHeader";
import { apiFetch } from "../lib/api";
import type { Job, Application } from "../types";

const STATUS_COLUMNS = [
  { id: "saved", label: "Saved", color: "border-zinc-600" },
  { id: "applied", label: "Applied", color: "border-blue-500" },
  { id: "interview", label: "Interview", color: "border-yellow-500" },
  { id: "offer", label: "Offer", color: "border-green-500" },
  { id: "rejected", label: "Rejected", color: "border-red-500" },
];

export default function TrackerPanel() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [view, setView] = useState<"board" | "list">("board");

  useEffect(() => {
    apiFetch("/api/jobs")
      .then((r) => r.json())
      .then(setJobs)
      .catch(() => {});
    apiFetch("/api/applications")
      .then((r) => r.json())
      .then(setApplications)
      .catch(() => {});
  }, []);

  async function createApplication(jobId: number) {
    try {
      await apiFetch(`/api/applications/${jobId}`, { method: "POST" });
      const apps = await apiFetch("/api/applications").then((r) => r.json());
      setApplications(apps);
    } catch {
      /* ignore */
    }
  }

  async function updateStatus(appId: number, status: string) {
    try {
      await apiFetch(`/api/applications/${appId}`, {
        method: "PATCH",
        body: JSON.stringify({ status }),
      });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status } : a))
      );
    } catch {
      /* ignore */
    }
  }

  const viewToggle = (
    <div className="flex gap-0.5 bg-zinc-800 rounded-lg p-0.5">
      <button
        onClick={() => setView("board")}
        className={`px-3 py-1.5 text-xs rounded-md ${
          view === "board"
            ? "bg-zinc-700 text-zinc-100"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        Board
      </button>
      <button
        onClick={() => setView("list")}
        className={`px-3 py-1.5 text-xs rounded-md ${
          view === "list"
            ? "bg-zinc-700 text-zinc-100"
            : "text-zinc-500 hover:text-zinc-300"
        }`}
      >
        List
      </button>
    </div>
  );

  return (
    <div className="flex flex-col h-full">
      <PanelHeader
        title="Application Tracker"
        subtitle={`${jobs.length} saved jobs — ${applications.length} applications`}
      >
        {viewToggle}
      </PanelHeader>

      <div className="flex-1 overflow-auto px-6 py-4">
        {view === "board" ? (
          <div className="flex gap-3 h-full min-w-max">
            {STATUS_COLUMNS.map((col) => {
              const colApps = applications.filter((a) => a.status === col.id);
              return (
                <div
                  key={col.id}
                  className={`w-56 flex-shrink-0 bg-zinc-900/30 rounded-xl border-t-2 ${col.color}`}
                >
                  <div className="p-3 border-b border-zinc-800">
                    <h3 className="text-sm font-medium text-zinc-300">
                      {col.label}{" "}
                      <span className="text-zinc-600">({colApps.length})</span>
                    </h3>
                  </div>
                  <div className="p-2 space-y-2 overflow-y-auto max-h-[calc(100vh-250px)]">
                    {colApps.map((app) => (
                      <div
                        key={app.id}
                        className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-3"
                      >
                        <p className="text-sm font-medium text-zinc-200 truncate">
                          {app.title}
                        </p>
                        <p className="text-xs text-zinc-500 truncate">
                          {app.company}
                        </p>
                        <div className="flex gap-1 mt-2 flex-wrap">
                          {STATUS_COLUMNS.filter(
                            (s) => s.id !== app.status
                          ).map((s) => (
                            <button
                              key={s.id}
                              onClick={() => updateStatus(app.id, s.id)}
                              className="text-[10px] text-zinc-600 hover:text-zinc-300 px-1.5 py-0.5 rounded hover:bg-zinc-800"
                              title={`Move to ${s.label}`}
                            >
                              {s.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                    {colApps.length === 0 && (
                      <p className="text-xs text-zinc-700 text-center py-4">
                        Empty
                      </p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="space-y-2 max-w-3xl">
            <h3 className="text-sm font-medium text-zinc-400 mb-3">
              Saved Jobs
            </h3>
            {jobs.length === 0 && (
              <p className="text-sm text-zinc-600">
                No saved jobs yet. Search and save jobs first.
              </p>
            )}
            {jobs.map((job) => {
              const hasApp = applications.some((a) => a.job_id === job.id);
              return (
                <div
                  key={job.id}
                  className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4 flex items-center justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-zinc-200">
                      {job.title}
                    </p>
                    <p className="text-xs text-zinc-500">
                      {job.company} — {job.location}
                    </p>
                    <p className="text-xs text-zinc-600 mt-1">
                      Saved {new Date(job.saved_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="p-2 rounded-lg text-zinc-500 hover:text-cyan-400 hover:bg-zinc-800"
                        title="View job"
                      >
                        <ExternalLink size={14} />
                      </a>
                    )}
                    {!hasApp && (
                      <button
                        onClick={() => createApplication(job.id)}
                        className="text-xs bg-zinc-800 text-zinc-400 px-3 py-1.5 rounded-lg hover:bg-indigo-600 hover:text-white"
                      >
                        Track
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
