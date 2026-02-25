import { useState, useEffect } from "react";
import type { Job, Application } from "../types";

const STATUS_COLUMNS = [
  { id: "saved", label: "Saved", color: "border-slate-500" },
  { id: "applied", label: "Applied", color: "border-blue-500" },
  { id: "interview", label: "Interview", color: "border-yellow-500" },
  { id: "offer", label: "Offer", color: "border-emerald-500" },
  { id: "rejected", label: "Rejected", color: "border-red-500" },
];

export default function TrackerPanel() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [applications, setApplications] = useState<Application[]>([]);
  const [view, setView] = useState<"board" | "list">("board");

  useEffect(() => {
    fetch("/api/jobs").then((r) => r.json()).then(setJobs).catch(() => {});
    fetch("/api/applications").then((r) => r.json()).then(setApplications).catch(() => {});
  }, []);

  async function createApplication(jobId: number) {
    try {
      await fetch(`/api/applications/${jobId}`, { method: "POST" });
      const apps = await fetch("/api/applications").then((r) => r.json());
      setApplications(apps);
    } catch {
      /* ignore */
    }
  }

  async function updateStatus(appId: number, status: string) {
    try {
      await fetch(`/api/applications/${appId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      });
      setApplications((prev) =>
        prev.map((a) => (a.id === appId ? { ...a, status } : a))
      );
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-slate-700 flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">Application Tracker</h2>
          <p className="text-xs text-slate-400">
            {jobs.length} saved jobs — {applications.length} applications
          </p>
        </div>
        <div className="flex gap-1 bg-slate-800 rounded-lg p-0.5">
          <button
            onClick={() => setView("board")}
            className={`px-3 py-1.5 text-xs rounded ${
              view === "board" ? "bg-slate-700 text-slate-100" : "text-slate-400"
            }`}
          >
            Board
          </button>
          <button
            onClick={() => setView("list")}
            className={`px-3 py-1.5 text-xs rounded ${
              view === "list" ? "bg-slate-700 text-slate-100" : "text-slate-400"
            }`}
          >
            List
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        {view === "board" ? (
          <div className="flex gap-3 h-full min-w-max">
            {STATUS_COLUMNS.map((col) => {
              const colApps = applications.filter((a) => a.status === col.id);
              return (
                <div
                  key={col.id}
                  className={`w-56 flex-shrink-0 bg-slate-800/50 rounded-lg border-t-2 ${col.color}`}
                >
                  <div className="p-3 border-b border-slate-700">
                    <h3 className="text-sm font-medium text-slate-200">
                      {col.label}{" "}
                      <span className="text-slate-500">({colApps.length})</span>
                    </h3>
                  </div>
                  <div className="p-2 space-y-2 overflow-y-auto max-h-[calc(100vh-250px)]">
                    {colApps.map((app) => (
                      <div
                        key={app.id}
                        className="bg-slate-800 border border-slate-700 rounded-lg p-3"
                      >
                        <p className="text-sm font-medium text-slate-200 truncate">
                          {app.title}
                        </p>
                        <p className="text-xs text-slate-400 truncate">{app.company}</p>
                        <div className="flex gap-1 mt-2">
                          {STATUS_COLUMNS.filter((s) => s.id !== app.status).map((s) => (
                            <button
                              key={s.id}
                              onClick={() => updateStatus(app.id, s.id)}
                              className="text-[10px] text-slate-500 hover:text-slate-300 px-1"
                              title={`Move to ${s.label}`}
                            >
                              {s.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                    {colApps.length === 0 && (
                      <p className="text-xs text-slate-600 text-center py-4">Empty</p>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="space-y-2">
            <h3 className="text-sm font-medium text-slate-300 mb-3">Saved Jobs</h3>
            {jobs.length === 0 && (
              <p className="text-sm text-slate-500">No saved jobs yet. Search and save jobs first.</p>
            )}
            {jobs.map((job) => {
              const hasApp = applications.some((a) => a.job_id === job.id);
              return (
                <div
                  key={job.id}
                  className="bg-slate-800 border border-slate-700 rounded-lg p-4 flex items-center justify-between"
                >
                  <div>
                    <p className="text-sm font-medium text-slate-200">{job.title}</p>
                    <p className="text-xs text-slate-400">
                      {job.company} — {job.location}
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Saved {new Date(job.saved_at).toLocaleDateString()}
                    </p>
                  </div>
                  <div className="flex gap-2">
                    {job.url && (
                      <a
                        href={job.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-emerald-400 hover:text-emerald-300"
                      >
                        View
                      </a>
                    )}
                    {!hasApp && (
                      <button
                        onClick={() => createApplication(job.id)}
                        className="text-xs bg-slate-700 text-slate-300 px-2 py-1 rounded hover:bg-emerald-600 hover:text-white"
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
