import { useState } from "react";
import { BarChart3, Upload } from "lucide-react";
import PanelHeader from "./PanelHeader";
import { apiFetch } from "../lib/api";
import type { AnalysisResult } from "../types";

export default function AnalyzePanel() {
  const [jdText, setJdText] = useState("");
  const [resumeText, setResumeText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState("");

  async function handleFileUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const text = await file.text();
    setResumeText(text);
  }

  async function analyze(e: React.FormEvent) {
    e.preventDefault();
    if (!jdText.trim() || !resumeText.trim() || loading) return;

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const res = await apiFetch("/api/analyze", {
        method: "POST",
        body: JSON.stringify({ jd_text: jdText, resume_text: resumeText }),
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
    const color =
      pct >= 70 ? "bg-teal-500" : pct >= 40 ? "bg-yellow-500" : "bg-red-500";
    return (
      <div className="flex items-center gap-3 text-sm">
        <span className="w-28 text-zinc-500 text-xs">{label}</span>
        <div className="flex-1 bg-zinc-800 rounded-full h-1.5">
          <div
            className={`${color} h-1.5 rounded-full`}
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="w-10 text-right text-zinc-300 text-xs tabular-nums">
          {pct}%
        </span>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <PanelHeader
        title="Job Analysis"
        subtitle="Paste a job description and your resume to get ATS score and skills match"
      />

      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        <form onSubmit={analyze} className="max-w-3xl space-y-4">
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Job Description</label>
            <textarea
              value={jdText}
              onChange={(e) => setJdText(e.target.value)}
              placeholder="Paste the full job description here..."
              rows={6}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 resize-y"
            />
          </div>
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-xs font-medium text-zinc-400">Your Resume</label>
              <label className="flex items-center gap-1.5 text-xs text-teal-400 cursor-pointer hover:text-teal-300">
                <Upload size={12} />
                <span>Upload .txt</span>
                <input
                  type="file"
                  accept=".txt,.md,.text"
                  onChange={handleFileUpload}
                  className="hidden"
                />
              </label>
            </div>
            <textarea
              value={resumeText}
              onChange={(e) => setResumeText(e.target.value)}
              placeholder="Paste your resume text here or upload a .txt file..."
              rows={6}
              className="w-full bg-zinc-900 border border-zinc-800 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-zinc-700 resize-y"
            />
          </div>
          <button
            type="submit"
            disabled={loading || !jdText.trim() || !resumeText.trim()}
            className="px-5 py-2.5 bg-teal-600 text-white rounded-xl text-sm font-medium hover:bg-teal-500 disabled:opacity-40 disabled:cursor-not-allowed"
          >
            {loading ? "Analyzing..." : "Analyze Against Resume"}
          </button>
        </form>

        {error && (
          <div className="max-w-3xl bg-red-900/20 border border-red-900/40 rounded-xl p-4 text-sm text-red-300">
            {error}
          </div>
        )}

        {result && (
          <div className="space-y-4 max-w-3xl">
            {/* ATS Score */}
            <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 size={16} className="text-zinc-500" />
                <h3 className="text-sm font-semibold text-zinc-100">ATS Score</h3>
                <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${
                  result.ats_score.grade === "STRONG" ? "bg-teal-500/20 text-teal-400" :
                  result.ats_score.grade === "MODERATE" ? "bg-yellow-500/20 text-yellow-400" :
                  "bg-red-500/20 text-red-400"
                }`}>
                  {result.ats_score.grade}
                </span>
              </div>
              <div className="text-center mb-5">
                <span
                  className={`text-5xl font-bold tabular-nums ${
                    result.ats_score.overall_score >= 70
                      ? "text-teal-400"
                      : result.ats_score.overall_score >= 40
                        ? "text-yellow-400"
                        : "text-red-400"
                  }`}
                >
                  {result.ats_score.overall_score}
                </span>
                <span className="text-zinc-600 text-lg">/100</span>
              </div>
              <div className="space-y-2.5">
                <ScoreBar label="Keywords" value={result.ats_score.keyword_analysis.keyword_match_rate / 100} />
                <ScoreBar label="Sections" value={result.ats_score.section_analysis.section_completeness / 100} />
                <ScoreBar label="Formatting" value={result.ats_score.formatting_analysis.formatting_score / 100} />
              </div>
            </div>

            {/* Missing Keywords */}
            {result.ats_score.keyword_analysis.missing_keywords.length > 0 ? (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-100 mb-3">
                  Missing Keywords
                </h3>
                <div className="flex flex-wrap gap-2">
                  {result.ats_score.keyword_analysis.missing_keywords.map((kw, i) => (
                    <span
                      key={i}
                      className="text-xs bg-red-900/30 text-red-300 border border-red-900/40 px-2 py-1 rounded-lg"
                    >
                      {kw}
                    </span>
                  ))}
                </div>
              </div>
            ) : null}

            {/* Suggestions */}
            {result.ats_score.suggestions.length > 0 ? (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-100 mb-3">
                  Suggestions
                </h3>
                <ul className="space-y-2">
                  {result.ats_score.suggestions.map((s, i) => (
                    <li
                      key={i}
                      className="text-sm text-zinc-300 flex gap-2"
                    >
                      <span className="text-teal-500 shrink-0">-</span>
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {/* JD Sections */}
            {result.jd_analysis.sections ? (
              <div className="bg-zinc-900/50 border border-zinc-800 rounded-xl p-5">
                <h3 className="text-sm font-semibold text-zinc-100 mb-3">
                  JD Breakdown
                </h3>
                <div className="space-y-3">
                  {Object.entries(
                    result.jd_analysis.sections as Record<string, string>
                  ).map(([section, content]) => (
                    <div key={section}>
                      <h4 className="text-xs font-medium text-teal-400 uppercase tracking-wide">
                        {section}
                      </h4>
                      <p className="text-sm text-zinc-400 mt-1 whitespace-pre-wrap">
                        {String(content)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
