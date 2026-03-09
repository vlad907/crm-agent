"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError, devLogin } from "@/src/lib/api";
import { setUserId, setWorkspaceId } from "@/src/lib/identity";

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
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!email.trim()) {
      setError("Email is required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    setMessage(null);

    try {
      const result = await devLogin({
        email: email.trim(),
        name: name.trim() || null
      });

      setWorkspaceId(result.workspace_id);
      setUserId(result.user_id);
      setMessage(result.created ? "Account created. Redirecting..." : "Welcome back. Redirecting...");
      router.push("/");
    } catch (loginError) {
      setError(getErrorMessage(loginError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Login</h1>
            <p className="page-subtitle">If the user does not exist yet, we create it automatically.</p>
          </div>
        </header>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <section className="card stack" style={{ maxWidth: 560 }}>
        <form className="stack" onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email *</label>
            <input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required />
          </div>

          <div className="field">
            <label htmlFor="name">Name (optional)</label>
            <input id="name" value={name} onChange={(event) => setName(event.target.value)} />
          </div>

          <div className="inline-actions">
            <button type="submit" className="btn-primary" disabled={submitting}>
              {submitting ? "Signing in..." : "Sign In"}
            </button>
            <Link href="/settings" className="btn-secondary btn-link">
              Identity Settings
            </Link>
          </div>
        </form>
      </section>
    </div>
  );
}
