import { useState, useEffect, useRef } from "react";
import {
  Save,
  Upload,
  Trash2,
  Star,
  FileText,
  Paperclip,
} from "lucide-react";
import { apiFetch } from "../lib/api";
import type { UserProfile, UserResume } from "../types";

export default function ProfilePanel() {
  const [profile, setProfile] = useState<UserProfile>({
    user_id: 0,
    target_role: "",
    experience_level: "",
    skills: [],
    bio: "",
    linkedin_url: "",
    github_username: "",
    location: "",
  });
  const [skillInput, setSkillInput] = useState("");
  const [resumes, setResumes] = useState<UserResume[]>([]);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    apiFetch("/api/profile")
      .then((r) => r.json())
      .then(setProfile)
      .catch(() => {});
    fetchResumes();
  }, []);

  async function fetchResumes() {
    try {
      const res = await apiFetch("/api/resumes");
      setResumes(await res.json());
    } catch {
      // ignore
    }
  }

  async function saveProfile() {
    setSaving(true);
    try {
      const res = await apiFetch("/api/profile", {
        method: "PUT",
        body: JSON.stringify(profile),
      });
      setProfile(await res.json());
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  }

  function addSkill() {
    const skill = skillInput.trim();
    if (skill && !profile.skills.includes(skill)) {
      setProfile({ ...profile, skills: [...profile.skills, skill] });
      setSkillInput("");
    }
  }

  function removeSkill(skill: string) {
    setProfile({ ...profile, skills: profile.skills.filter((s) => s !== skill) });
  }

  async function handleResumeUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    e.target.value = "";

    let content: string;
    const ext = file.name.split(".").pop()?.toLowerCase();

    if (ext === "pdf") {
      const formData = new FormData();
      formData.append("file", file);
      try {
        const res = await apiFetch("/api/extract-text", { method: "POST", body: formData });
        const data = await res.json();
        content = data.text;
      } catch {
        return;
      }
    } else {
      content = await file.text();
    }

    const isFirst = resumes.length === 0;
    await apiFetch("/api/resumes", {
      method: "POST",
      body: JSON.stringify({ name: file.name, content, is_default: isFirst }),
    });
    fetchResumes();
  }

  async function deleteResume(id: number) {
    await apiFetch(`/api/resumes/${id}`, { method: "DELETE" });
    fetchResumes();
  }

  async function setDefault(id: number) {
    await apiFetch(`/api/resumes/${id}/default`, { method: "PATCH" });
    fetchResumes();
  }

  const inputClass =
    "w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-indigo-500";

  return (
    <div className="h-full overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 py-8 space-y-8">
        {/* Header */}
        <div>
          <h2 className="text-xl font-semibold text-zinc-100">Profile</h2>
          <p className="text-sm text-zinc-500 mt-1">
            Help Kazi understand your background so it can give personalized advice.
          </p>
        </div>

        {/* Profile form */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-5">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Target Role</label>
              <input
                className={inputClass}
                placeholder="e.g. Senior Backend Engineer"
                value={profile.target_role}
                onChange={(e) => setProfile({ ...profile, target_role: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Experience Level</label>
              <select
                className={inputClass}
                value={profile.experience_level}
                onChange={(e) => setProfile({ ...profile, experience_level: e.target.value })}
              >
                <option value="">Select...</option>
                <option value="Entry-level">Entry-level (0-2 years)</option>
                <option value="Mid-level">Mid-level (3-5 years)</option>
                <option value="Senior">Senior (6-10 years)</option>
                <option value="Staff/Principal">Staff/Principal (10+ years)</option>
                <option value="Executive">Executive / C-level</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">Location</label>
              <input
                className={inputClass}
                placeholder="e.g. Nairobi, Kenya"
                value={profile.location}
                onChange={(e) => setProfile({ ...profile, location: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-zinc-400 mb-1.5">GitHub Username</label>
              <input
                className={inputClass}
                placeholder="e.g. octocat"
                value={profile.github_username}
                onChange={(e) => setProfile({ ...profile, github_username: e.target.value })}
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">LinkedIn URL</label>
            <input
              className={inputClass}
              placeholder="https://linkedin.com/in/yourname"
              value={profile.linkedin_url}
              onChange={(e) => setProfile({ ...profile, linkedin_url: e.target.value })}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Bio</label>
            <textarea
              className={inputClass + " resize-none h-20"}
              placeholder="Brief professional summary..."
              value={profile.bio}
              onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
            />
          </div>

          {/* Skills */}
          <div>
            <label className="block text-xs font-medium text-zinc-400 mb-1.5">Skills</label>
            <div className="flex gap-2 mb-2">
              <input
                className={inputClass}
                placeholder="Add a skill..."
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    addSkill();
                  }
                }}
              />
              <button
                type="button"
                onClick={addSkill}
                className="px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700 shrink-0"
              >
                Add
              </button>
            </div>
            {profile.skills.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {profile.skills.map((skill) => (
                  <span
                    key={skill}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 bg-indigo-600/15 text-indigo-300 rounded-full text-xs"
                  >
                    {skill}
                    <button
                      onClick={() => removeSkill(skill)}
                      className="hover:text-indigo-100"
                    >
                      &times;
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Auto-suggestions toggle */}
          <div className="flex items-center justify-between">
            <div>
              <label className="block text-xs font-medium text-zinc-400">Auto-suggestions</label>
              <p className="text-xs text-zinc-600 mt-0.5">
                AI will proactively suggest goals based on your activity
              </p>
            </div>
            <button
              type="button"
              onClick={() => setProfile({ ...profile, auto_suggestions: profile.auto_suggestions === false ? true : (profile.auto_suggestions === true ? false : false) } as typeof profile)}
              className={`relative inline-flex h-6 w-11 items-center rounded-full ${
                profile.auto_suggestions !== false ? "bg-indigo-600" : "bg-zinc-700"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 rounded-full bg-white ${
                  profile.auto_suggestions !== false ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
          </div>

          <button
            onClick={saveProfile}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm rounded-lg hover:bg-indigo-500 disabled:opacity-50"
          >
            <Save size={14} />
            {saved ? "Saved!" : saving ? "Saving..." : "Save Profile"}
          </button>
        </div>

        {/* Resumes section */}
        <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-6 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-base font-medium text-zinc-100">Resumes</h3>
              <p className="text-xs text-zinc-500 mt-0.5">
                Upload resumes so Kazi can reference them in conversations.
              </p>
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".txt,.md,.text,.pdf"
              className="hidden"
              onChange={handleResumeUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-300 hover:bg-zinc-700"
            >
              <Upload size={14} />
              Upload
            </button>
          </div>

          {resumes.length === 0 ? (
            <div className="text-center py-8">
              <Paperclip size={24} className="text-zinc-600 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No resumes uploaded yet</p>
              <p className="text-xs text-zinc-600 mt-1">
                Upload a .txt, .md, or .pdf file
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {resumes.map((resume) => (
                <div
                  key={resume.id}
                  className="flex items-center gap-3 p-3 bg-zinc-800/50 border border-zinc-700/50 rounded-lg"
                >
                  <FileText size={16} className="text-zinc-500 shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-200 truncate">{resume.name}</p>
                    <p className="text-xs text-zinc-500">
                      {Math.round(resume.char_count / 1000)}k chars
                      {resume.is_default ? " \u00B7 Default" : ""}
                    </p>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    {!resume.is_default && (
                      <button
                        onClick={() => setDefault(resume.id)}
                        className="p-1.5 rounded text-zinc-500 hover:text-yellow-400 hover:bg-zinc-700"
                        title="Set as default"
                      >
                        <Star size={14} />
                      </button>
                    )}
                    {resume.is_default && (
                      <span className="p-1.5 text-yellow-400" title="Default resume">
                        <Star size={14} fill="currentColor" />
                      </span>
                    )}
                    <button
                      onClick={() => deleteResume(resume.id)}
                      className="p-1.5 rounded text-zinc-500 hover:text-red-400 hover:bg-zinc-700"
                      title="Delete resume"
                    >
                      <Trash2 size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
