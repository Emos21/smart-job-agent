import { useState } from "react";
import { Eye, EyeOff } from "lucide-react";
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
        const data = await res.json();
        throw new Error(data.detail || "Something went wrong");
      }

      const data: AuthResponse = await res.json();
      setToken(data.token);
      onAuth(data.user);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center relative overflow-hidden"
      style={{ backgroundColor: "#eeece2" }}
    >
      {/* Subtle decorative elements */}
      <svg
        className="absolute inset-0 w-full h-full pointer-events-none"
        xmlns="http://www.w3.org/2000/svg"
      >
        {/* Large warm glow - top right */}
        <radialGradient id="glow1" cx="75%" cy="20%" r="35%">
          <stop offset="0%" stopColor="#da7756" stopOpacity="0.06" />
          <stop offset="100%" stopColor="#da7756" stopOpacity="0" />
        </radialGradient>
        <rect width="100%" height="100%" fill="url(#glow1)" />

        {/* Subtle glow - bottom left */}
        <radialGradient id="glow2" cx="20%" cy="80%" r="30%">
          <stop offset="0%" stopColor="#da7756" stopOpacity="0.04" />
          <stop offset="100%" stopColor="#da7756" stopOpacity="0" />
        </radialGradient>
        <rect width="100%" height="100%" fill="url(#glow2)" />

        {/* Delicate constellation dots */}
        <circle cx="12%" cy="18%" r="1.5" fill="#c4a882" opacity="0.3" />
        <circle cx="15%" cy="22%" r="1" fill="#c4a882" opacity="0.2" />
        <circle cx="10%" cy="25%" r="0.8" fill="#c4a882" opacity="0.25" />
        <line x1="12%" y1="18%" x2="15%" y2="22%" stroke="#c4a882" strokeWidth="0.3" opacity="0.15" />
        <line x1="15%" y1="22%" x2="10%" y2="25%" stroke="#c4a882" strokeWidth="0.3" opacity="0.15" />

        <circle cx="85%" cy="72%" r="1.5" fill="#c4a882" opacity="0.3" />
        <circle cx="88%" cy="68%" r="1" fill="#c4a882" opacity="0.2" />
        <circle cx="82%" cy="75%" r="0.8" fill="#c4a882" opacity="0.25" />
        <line x1="85%" y1="72%" x2="88%" y2="68%" stroke="#c4a882" strokeWidth="0.3" opacity="0.15" />
        <line x1="85%" y1="72%" x2="82%" y2="75%" stroke="#c4a882" strokeWidth="0.3" opacity="0.15" />

        <circle cx="72%" cy="15%" r="1" fill="#c4a882" opacity="0.2" />
        <circle cx="30%" cy="85%" r="1" fill="#c4a882" opacity="0.2" />
        <circle cx="92%" cy="45%" r="0.8" fill="#c4a882" opacity="0.15" />
        <circle cx="5%" cy="55%" r="0.8" fill="#c4a882" opacity="0.15" />
      </svg>

      {/* Auth card */}
      <div className="relative z-10 w-full max-w-sm mx-4">
        <div
          className="rounded-2xl p-10 shadow-sm"
          style={{
            backgroundColor: "#faf9f5",
            border: "1px solid #e2dfd3",
          }}
        >
          {/* Branding */}
          <div className="text-center mb-10">
            {/* Briefcase icon in warm style */}
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
              style={{ backgroundColor: "rgba(218, 119, 86, 0.1)" }}
            >
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path
                  d="M20 7H4C2.89543 7 2 7.89543 2 9V19C2 20.1046 2.89543 21 4 21H20C21.1046 21 22 20.1046 22 19V9C22 7.89543 21.1046 7 20 7Z"
                  stroke="#da7756"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M16 7V5C16 3.89543 15.1046 3 14 3H10C8.89543 3 8 3.89543 8 5V7"
                  stroke="#da7756"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                <path
                  d="M12 12V12.01"
                  stroke="#da7756"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
                <path
                  d="M2 12H22"
                  stroke="#da7756"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  opacity="0.4"
                />
              </svg>
            </div>
            <h1
              className="text-3xl font-semibold tracking-tight"
              style={{
                color: "#3d3929",
                fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
              }}
            >
              KaziAI
            </h1>
            <p
              className="text-sm mt-2"
              style={{ color: "#8b8578" }}
            >
              {isLogin
                ? "Welcome back. Sign in to continue."
                : "Create an account to get started."}
            </p>
          </div>

          {/* Error */}
          {error && (
            <div
              className="mb-5 rounded-xl px-4 py-3 text-sm"
              style={{
                backgroundColor: "rgba(189, 93, 58, 0.08)",
                border: "1px solid rgba(189, 93, 58, 0.2)",
                color: "#9a3412",
              }}
            >
              {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {!isLogin && (
              <div>
                <label
                  className="block text-xs font-medium mb-1.5"
                  style={{ color: "#6b6558" }}
                >
                  Name
                </label>
                <input
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your name"
                  className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                  style={{
                    backgroundColor: "#ffffff",
                    border: "1px solid #d8d4c8",
                    color: "#3d3929",
                    fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "#bd5d3a")}
                  onBlur={(e) => (e.target.style.borderColor = "#d8d4c8")}
                />
              </div>
            )}

            <div>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6b6558" }}
              >
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="w-full rounded-xl px-4 py-3 text-sm outline-none"
                style={{
                  backgroundColor: "#ffffff",
                  border: "1px solid #d8d4c8",
                  color: "#3d3929",
                  fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
                }}
                onFocus={(e) => (e.target.style.borderColor = "#bd5d3a")}
                onBlur={(e) => (e.target.style.borderColor = "#d8d4c8")}
              />
            </div>

            <div>
              <label
                className="block text-xs font-medium mb-1.5"
                style={{ color: "#6b6558" }}
              >
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
                  className="w-full rounded-xl px-4 py-3 pr-10 text-sm outline-none"
                  style={{
                    backgroundColor: "#ffffff",
                    border: "1px solid #d8d4c8",
                    color: "#3d3929",
                    fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
                  }}
                  onFocus={(e) => (e.target.style.borderColor = "#bd5d3a")}
                  onBlur={(e) => (e.target.style.borderColor = "#d8d4c8")}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2"
                  style={{ color: "#8b8578" }}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={loading}
                className="w-full rounded-xl py-3 text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                style={{
                  backgroundColor: "#bd5d3a",
                  color: "#ffffff",
                  fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
                }}
                onMouseEnter={(e) => {
                  if (!loading) (e.target as HTMLButtonElement).style.backgroundColor = "#da7756";
                }}
                onMouseLeave={(e) => {
                  (e.target as HTMLButtonElement).style.backgroundColor = "#bd5d3a";
                }}
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
            <div className="flex-1 h-px" style={{ backgroundColor: "#e2dfd3" }} />
            <span className="text-xs" style={{ color: "#a09a8d" }}>or</span>
            <div className="flex-1 h-px" style={{ backgroundColor: "#e2dfd3" }} />
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
            className="w-full rounded-xl py-3 text-sm font-medium"
            style={{
              backgroundColor: "transparent",
              border: "1px solid #d8d4c8",
              color: "#3d3929",
              fontFamily: "ui-serif, Georgia, Cambria, 'Times New Roman', Times, serif",
            }}
            onMouseEnter={(e) => (e.target as HTMLButtonElement).style.backgroundColor = "rgba(218, 119, 86, 0.05)"}
            onMouseLeave={(e) => (e.target as HTMLButtonElement).style.backgroundColor = "transparent"}
          >
            {isLogin ? "Create a new account" : "Sign in to existing account"}
          </button>
        </div>

        {/* Footer text */}
        <p
          className="text-center text-xs mt-6"
          style={{ color: "#a09a8d" }}
        >
          Your AI-powered career assistant
        </p>
      </div>
    </div>
  );
}
