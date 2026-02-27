import { useState } from "react";
import { Eye, EyeOff, Briefcase } from "lucide-react";
import { GoogleLogin } from "@react-oauth/google";
import type { User, AuthResponse } from "../types";
import { setToken } from "../lib/api";

interface AuthPageProps {
  onAuth: (user: User) => void;
}

export default function AuthPage({ onAuth }: AuthPageProps) {
  const [isLogin, setIsLogin] = useState(true);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);

    const endpoint = isLogin ? "/api/auth/login" : "/api/auth/register";
    const body = isLogin
      ? { email, password }
      : { email, password, name };

    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        let detail = "Something went wrong";
        try {
          const data = await res.json();
          detail = data.detail || detail;
        } catch {
          detail = `Server error (${res.status})`;
        }
        throw new Error(detail);
      }

      let data: AuthResponse;
      try {
        data = await res.json();
      } catch {
        throw new Error("Invalid response from server. Is the backend running?");
      }
      setToken(data.token);
      onAuth(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 relative overflow-hidden">
      {/* Subtle decorative gradients */}
      <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-600/5 rounded-full blur-3xl" />
      <div className="absolute bottom-0 left-0 w-80 h-80 bg-cyan-500/5 rounded-full blur-3xl" />

      {/* Auth card */}
      <div className="relative z-10 w-full max-w-sm mx-4">
        <div className="bg-zinc-900 border border-zinc-800 rounded-2xl p-10 shadow-lg">
          {/* Branding */}
          <div className="text-center mb-10">
            <div className="w-16 h-16 rounded-2xl bg-indigo-600/10 flex items-center justify-center mx-auto mb-5">
              <Briefcase size={32} className="text-indigo-400" />
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-cyan-400">
              KaziAI
            </h1>
            <p className="text-sm mt-2 text-zinc-500">
              {isLogin
                ? "Welcome back. Sign in to continue."
                : "Create an account to get started."}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div className="mb-5 rounded-xl px-4 py-3 text-sm bg-red-900/20 border border-red-900/40 text-red-300">
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label className="block text-xs font-medium mb-1.5 text-zinc-400">
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-indigo-500"
                />
              </div>
            )}

            <div>
              <label className="block text-xs font-medium mb-1.5 text-zinc-400">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-indigo-500"
              />
            </div>

            <div>
              <label className="block text-xs font-medium mb-1.5 text-zinc-400">
                Password
              </label>
              <div className="relative">
                <input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={isLogin ? "Enter password" : "At least 6 characters"}
                  required
                  minLength={6}
                  className="w-full bg-zinc-800 border border-zinc-700 rounded-xl px-4 py-3 pr-10 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-indigo-500"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full bg-indigo-600 text-white rounded-xl py-3 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading
                  ? "Please wait..."
                  : isLogin
                    ? "Continue"
                    : "Create Account"}
              </button>
            </div>
          </form>

          {/* Divider */}
          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-zinc-800" />
            <span className="text-xs text-zinc-600">or</span>
            <div className="flex-1 h-px bg-zinc-800" />
          </div>

          {/* Google Sign-In */}
          <div className="flex justify-center mb-4">
            <GoogleLogin
              onSuccess={async (credentialResponse) => {
                setError("");
                if (!credentialResponse.credential) {
                  setError("Google sign-in failed: no credential returned");
                  return;
                }
                try {
                  const res = await fetch("/api/auth/google", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ credential: credentialResponse.credential }),
                  });
                  if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.detail || "Google sign-in failed");
                  }
                  const data: AuthResponse = await res.json();
                  setToken(data.token);
                  onAuth(data.user);
                } catch (err) {
                  setError(err instanceof Error ? err.message : "Google sign-in failed");
                }
              }}
              onError={() => {
                setError("Google sign-in was cancelled or failed");
              }}
              size="large"
              width={308}
              text={isLogin ? "signin_with" : "signup_with"}
            />
          </div>

          {/* Toggle */}
          <button
            onClick={() => {
              setIsLogin(!isLogin);
              setError("");
            }}
            className="w-full border border-zinc-700 text-zinc-300 rounded-xl py-3 text-sm font-medium hover:bg-zinc-800 hover:text-zinc-100"
          >
            {isLogin ? "Create a new account" : "Sign in to existing account"}
          </button>
        </div>

        {/* Footer text */}
        <p className="text-center text-xs mt-6 text-zinc-600">
          Your AI-powered career assistant
        </p>
      </div>
    </div>
  );
}
