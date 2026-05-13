"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { ApiError, devLogin, getApiBase } from "@/src/lib/api";
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

async function fetchGoogleConnectUrl(): Promise<{ url: string } | { error: string }> {
  try {
    const res = await fetch(`${getApiBase()}/api/v1/auth/google/connect-url`);
    const text = await res.text().catch(() => "");
    if (!res.ok) {
      // Try to parse detail from JSON; fall back to helpful default
      let detail = "Google sign-in is not configured. Add your Google OAuth credentials in Settings → Integrations.";
      try {
        const body = JSON.parse(text) as { detail?: string };
        if (body.detail) detail = body.detail;
      } catch { /* not JSON — use default */ }
      return { error: detail };
    }
    const body = JSON.parse(text) as { connect_url?: string };
    if (!body.connect_url?.startsWith("https://")) {
      return { error: "Invalid Google OAuth URL returned. Check your credentials in Settings → Integrations." };
    }
    return { url: body.connect_url };
  } catch {
    return { error: "Could not reach the backend. Make sure the app has finished starting up." };
  }
}

function LoginPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [checking, setChecking] = useState(true);
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [googleConfigured, setGoogleConfigured] = useState<boolean | null>(null); // null = unknown
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (hasIdentity()) {
      router.replace("/");
      return;
    }

    // Handle redirect back from Google OAuth
    const googleAuth = searchParams.get("google_auth");
    if (googleAuth === "success") {
      const wsId = searchParams.get("workspace_id");
      const uId = searchParams.get("user_id");
      const isNew = searchParams.get("created") === "1";
      if (wsId && uId) {
        setWorkspaceId(wsId);
        setUserId(uId);
        setMessage(isNew ? "Account created. Setting up your workspace…" : "Signed in with Google. Redirecting...");
        router.replace(isNew ? "/onboarding" : "/");
        return;
      }
    }
    if (googleAuth === "error") {
      const msg = searchParams.get("message") || "Google sign-in failed.";
      setError(msg);
    }

    // Pre-check if Google OAuth is configured so we can show the right button state
    void fetchGoogleConnectUrl().then((result) => {
      setGoogleConfigured(!("error" in result));
    });

    setChecking(false);
  }, [router, searchParams]);

  async function onGoogleSignIn(): Promise<void> {
    setGoogleLoading(true);
    setError(null);
    const result = await fetchGoogleConnectUrl();
    if ("error" in result) {
      setError(result.error);
      setGoogleConfigured(false);
      setGoogleLoading(false);
      return;
    }
    window.location.href = result.url;
  }

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

        {/* Google Sign-In */}
        <button
          type="button"
          className="google-signin-btn"
          disabled={googleLoading || submitting || googleConfigured === false}
          title={googleConfigured === false ? "Google sign-in requires OAuth credentials — configure them in Settings → Integrations." : undefined}
          onClick={() => void onGoogleSignIn()}
        >
          {googleLoading ? (
            <span>Redirecting to Google…</span>
          ) : (
            <>
              <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"/>
                <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"/>
                <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z"/>
                <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z"/>
              </svg>
              <span>Sign in with Google</span>
            </>
          )}
        </button>
        {googleConfigured === false ? (
          <p style={{ fontSize: ".78rem", color: "var(--text-muted)", textAlign: "center", margin: "-2px 0 6px" }}>
            Requires Google OAuth credentials — set up in <strong>Settings → Integrations</strong>.
          </p>
        ) : null}

        <div className="login-divider"><span>or</span></div>

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

export default function LoginPage() {
  return (
    <Suspense fallback={<div className="login-page-wrap"><div className="app-shell-spinner" style={{ position: "relative", zIndex: 2 }} /></div>}>
      <LoginPageInner />
    </Suspense>
  );
}
