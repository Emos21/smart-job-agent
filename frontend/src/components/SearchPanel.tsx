import { useState } from "react";
import { Search, Bookmark } from "lucide-react";
import PanelHeader from "./PanelHeader";
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
          keywords: keywords
            .split(",")
            .map((k) => k.trim())
            .filter(Boolean),
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
      <PanelHeader title="Job Search" subtitle="Search across multiple job boards" />

      <form onSubmit={search} className="px-6 py-4 border-b border-zinc-800">
        <div className="flex gap-2 max-w-3xl">
          <div className="flex-1 flex items-center gap-2 bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-2.5 focus-within:border-zinc-700">
            <Search size={16} className="text-zinc-500 shrink-0" />
            <input
              type="text"
              value={keywords}
              onChange={(e) => setKeywords(e.target.value)}
              placeholder="python, backend, senior engineer..."
              className="flex-1 bg-transparent text-sm text-zinc-100 placeholder-zinc-600 outline-none"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !keywords.trim()}
            className="px-5 bg-teal-600 text-white rounded-xl text-sm font-medium hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Searching..." : "Search"}
          </button>
        </div>
      </form>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {!searched && (
          <div className="text-center text-zinc-600 mt-20">
            <Search size={32} className="mx-auto mb-3 text-zinc-700" />
            <p className="text-sm">Enter keywords to search for jobs</p>
          </div>
        )}

        {searched && !loading && results.length === 0 && (
          <div className="text-center text-zinc-500 mt-20">
            <p className="text-sm">No jobs found. Try different keywords.</p>
          </div>
        )}

        {results.length > 0 && (
          <>
            <p className="text-sm text-zinc-500 mb-4">
              Found {totalFound} jobs — showing {results.length}
            </p>
            <div className="space-y-3 max-w-3xl">
              {results.map((job, i) => (
                <div
                  key={i}
                  className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-4"
                >
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <h3 className="text-sm font-medium text-zinc-100">
                        {job.url ? (
                          <a
                            href={job.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="hover:text-teal-400"
                          >
                            {job.title}
                          </a>
                        ) : (
                          job.title
                        )}
                      </h3>
                      <p className="text-xs text-zinc-500 mt-1">
                        {job.company} — {job.location}
                      </p>
                      {job.salary && (
                        <p className="text-xs text-teal-400 mt-1">{job.salary}</p>
                      )}
                      <div className="flex gap-1.5 mt-2 flex-wrap">
                        {job.tags.slice(0, 5).map((tag, j) => (
                          <span
                            key={j}
                            className="text-xs bg-zinc-800 text-zinc-400 px-2 py-0.5 rounded-md"
                          >
                            {tag}
                          </span>
                        ))}
                        <span className="text-xs text-zinc-600">{job.source}</span>
                      </div>
                    </div>
                    <button
                      onClick={() => saveJob(job, i)}
                      disabled={saving === i}
                      className="ml-3 p-2 rounded-lg text-zinc-500 hover:text-teal-400 hover:bg-zinc-800 disabled:opacity-50"
                      title="Save job"
                    >
                      <Bookmark size={16} />
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
