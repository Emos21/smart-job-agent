import { useState } from "react";
import type { SearchJob } from "../types";

export default function SearchPanel() {
  const [keywords, setKeywords] = useState("");
  const [results, setResults] = useState<SearchJob[]>([]);
  const [totalFound, setTotalFound] = useState(0);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);
  const [saving, setSaving] = useState<number | null>(null);

  async function search(e: React.FormEvent) {
    e.preventDefault();
    if (!keywords.trim() || loading) return;

    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keywords: keywords.split(",").map((k) => k.trim()).filter(Boolean),
          max_results: 15,
        }),
      });
      const data = await res.json();
      setResults(data.jobs || []);
      setTotalFound(data.total_found || 0);
    } catch {
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  async function saveJob(job: SearchJob, index: number) {
    setSaving(index);
    try {
      await fetch("/api/jobs/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: job.title,
          company: job.company,
          location: job.location,
          url: job.url,
          source: job.source,
          tags: job.tags,
        }),
      });
    } finally {
      setSaving(null);
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-slate-100">Job Search</h2>
        <p className="text-xs text-slate-400">Search across multiple job boards</p>
      </div>

      <form onSubmit={search} className="p-4 border-b border-slate-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={keywords}
            onChange={(e) => setKeywords(e.target.value)}
            placeholder="python, backend, senior engineer..."
            className="flex-1 bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500"
          />
          <button
            type="submit"
            disabled={loading || !keywords.trim()}
            className="px-6 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      <div className="flex-1 overflow-y-auto p-4">
        {!searched && (
          <div className="text-center text-slate-500 mt-20">
            <p className="text-4xl mb-4">🔍</p>
            <p className="text-sm">Enter keywords to search for jobs</p>
          </div>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="text-center text-slate-500 mt-20">
            <p className="text-sm">No jobs found. Try different keywords.</p>
          </div>
        )}

        {results.length > 0 && (
          <>
            <p className="text-sm text-slate-400 mb-4">
              Found {totalFound} jobs — showing {results.length}
            </p>
            <div className="space-y-3">
              {results.map((job, i) => (
                <div
                  key={i}
                  className="bg-slate-800 border border-slate-700 rounded-lg p-4"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-slate-100">
                        {job.url ? (
                          <a
                            href={job.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-emerald-400"
                          >
                            {job.title}
                          </a>
                        ) : (
                          job.title
                        )}
                      </h3>
                      <p className="text-xs text-slate-400 mt-1">
                        {job.company} — {job.location}
                      </p>
                      {job.salary && (
                        <p className="text-xs text-emerald-400 mt-1">{job.salary}</p>
                      )}
                      <div className="flex gap-1 mt-2 flex-wrap">
                        {job.tags.slice(0, 5).map((tag, j) => (
                          <span
                            key={j}
                            className="text-xs bg-slate-700 text-slate-300 px-2 py-0.5 rounded"
                          >
                            {tag}
                          </span>
                        ))}
                        <span className="text-xs text-slate-500">{job.source}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => saveJob(job, i)}
                      disabled={saving === i}
                      className="ml-3 px-3 py-1.5 text-xs bg-slate-700 text-slate-300 rounded hover:bg-emerald-600 hover:text-white disabled:opacity-50"
                    >
                      {saving === i ? "Saving..." : "Save"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
