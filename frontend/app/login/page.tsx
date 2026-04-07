"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { ApiError, devLogin } from "@/src/lib/api";
import { setUserId, setWorkspaceId, hasIdentity } from "@/src/lib/identity";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function LoginPage() {
  const router = useRouter();
  const [checking, setChecking] = useState(true);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (hasIdentity()) {
      router.replace("/");
      return;
    }
    setChecking(false);
  }, [router]);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }
    if (!password.trim()) {
      setError(mode === "signup" ? "Password is required to create an account." : "Password is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setMessage(null);

    try {
      const result = await devLogin({
        email: email.trim().toLowerCase(),
        username: mode === "signup" ? username.trim() || null : undefined,
        password: password || null
      });

      if (mode === "signup" && !result.created) {
        setError("An account with this email already exists. Sign in instead or use a different email.");
        setSubmitting(false);
        return;
      }

      setWorkspaceId(result.workspace_id);
      setUserId(result.user_id);
      setMessage(result.created ? "Account created. Redirecting to setup..." : "Welcome back. Redirecting...");
      router.push(result.created ? "/onboarding" : "/");
    } catch (loginError) {
      setError(getErrorMessage(loginError));
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) {
    return (
      <div className="login-page-wrap">
        <div className="app-shell-spinner" style={{ position: "relative", zIndex: 2 }} />
      </div>
    );
  }

  return (
    <div className="login-page-wrap">
      <div className="login-card">
        <Link href="/" className="login-brand">
          <span className="login-brand-text">
            CRM <span>Command</span>
          </span>
        </Link>

        <div className="login-mode-tabs">
          <button
            type="button"
            className={`login-mode-tab ${mode === "signin" ? "active" : ""}`}
            onClick={() => setMode("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            className={`login-mode-tab ${mode === "signup" ? "active" : ""}`}
            onClick={() => setMode("signup")}
          >
            Create account
          </button>
        </div>

        <h1>{mode === "signup" ? "Create your account" : "Sign in"}</h1>
        <p className="login-subtitle">
          {mode === "signup"
            ? "Enter your details to get started"
            : "Enter your credentials to access your pipeline"}
        </p>

        {error ? <div className="error">{error}</div> : null}
        {message ? <div className="success">{message}</div> : null}

        <form className="stack" onSubmit={onSubmit}>
          {mode === "signup" && (
            <div className="field">
              <label htmlFor="username">Username (optional)</label>
              <input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="johndoe"
                autoComplete="username"
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="email">Email *</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoComplete="email"
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password *</label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              autoComplete="current-password"
            />
          </div>

          <div className="inline-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting
                ? mode === "signup"
                  ? "Creating account..."
                  : "Signing in..."
                : mode === "signup"
                  ? "Create account"
                  : "Sign in"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
