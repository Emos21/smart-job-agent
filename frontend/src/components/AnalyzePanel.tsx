import { useState } from "react";
import type { AnalysisResult } from "../types";

export default function AnalyzePanel() {
  const [jdText, setJdText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!jdText.trim() || loading) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jd_text: jdText }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  function ScoreBar({ label, value }: { label: string; value: number }) {
    const pct = Math.round(value * 100);
    const color = pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="w-28 text-slate-400">{label}</span>
        <div className="flex-1 bg-slate-700 rounded-full h-2">
          <div className={`${color} h-2 rounded-full`} style={{ width: `${pct}%` }} />
        </div>
        <span className="w-10 text-right text-slate-300">{pct}%</span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-slate-700">
        <h2 className="text-lg font-semibold text-slate-100">Job Analysis</h2>
        <p className="text-xs text-slate-400">
          Paste a job description to get ATS score and skills match
        </p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <form onSubmit={analyze}>
          <textarea
            value={jdText}
            onChange={(e) => setJdText(e.target.value)}
            placeholder="Paste the full job description here..."
            rows={8}
            className="w-full bg-slate-800 border border-slate-600 rounded-lg px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-emerald-500 resize-y"
          />
          <button
            type="submit"
            disabled={loading || !jdText.trim()}
            className="mt-2 px-6 py-2.5 bg-emerald-600 text-white rounded-lg text-sm font-medium hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Analyzing..." : "Analyze Against Resume"}
          </button>
        </form>

        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-6">
            {/* ATS Score */}
            <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
              <h3 className="text-md font-semibold text-slate-100 mb-4">ATS Score</h3>
              <div className="text-center mb-4">
                <span
                  className={`text-5xl font-bold ${
                    result.ats_score.score >= 70
                      ? "text-emerald-400"
                      : result.ats_score.score >= 40
                        ? "text-yellow-400"
                        : "text-red-400"
                  }`}
                >
                  {result.ats_score.score}
                </span>
                <span className="text-slate-500 text-lg">/100</span>
              </div>
              <div className="space-y-2">
                {result.ats_score.breakdown && Object.entries(result.ats_score.breakdown).map(([key, val]) => (
                  <ScoreBar key={key} label={key} value={val} />
                ))}
              </div>
            </div>

            {/* Missing Keywords */}
            {result.ats_score.missing_keywords.length > 0 ? (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
                <h3 className="text-md font-semibold text-slate-100 mb-3">Missing Keywords</h3>
                <div className="flex flex-wrap gap-2">
                  {result.ats_score.missing_keywords.map((kw, i) => (
                    <span
                      key={i}
                      className="text-xs bg-red-900/40 text-red-300 border border-red-700 px-2 py-1 rounded"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Suggestions */}
            {result.ats_score.suggestions.length > 0 ? (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
                <h3 className="text-md font-semibold text-slate-100 mb-3">Suggestions</h3>
                <ul className="space-y-2">
                  {result.ats_score.suggestions.map((s, i) => (
                    <li key={i} className="text-sm text-slate-300 flex gap-2">
                      <span className="text-emerald-400 shrink-0">-</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* JD Sections */}
            {result.jd_analysis.sections ? (
              <div className="bg-slate-800 border border-slate-700 rounded-lg p-5">
                <h3 className="text-md font-semibold text-slate-100 mb-3">JD Breakdown</h3>
                <div className="space-y-3">
                  {Object.entries(result.jd_analysis.sections as Record<string, string>).map(
                    ([section, content]) => (
                      <div key={section}>
                        <h4 className="text-xs font-medium text-emerald-400 uppercase tracking-wide">
                          {section}
                        </h4>
                        <p className="text-sm text-slate-300 mt-1 whitespace-pre-wrap">{String(content)}</p>
                      </div>
                    )
                  )}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
