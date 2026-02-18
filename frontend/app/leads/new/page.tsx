"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { ApiError, createLead } from "@/src/lib/api";

interface LeadFormState {
  name: string;
  company: string;
  website_url: string;
  email: string;
  location: string;
  industry: string;
  status: string;
  source: string;
}

const initialState: LeadFormState = {
  name: "",
  company: "",
  website_url: "",
  email: "",
  location: "",
  industry: "",
  status: "new",
  source: "manual"
};

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

export default function NewLeadPage() {
  const router = useRouter();
  const [form, setForm] = useState<LeadFormState>(initialState);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function updateField(field: keyof LeadFormState, value: string): void {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    if (!form.name.trim() || !form.company.trim()) {
      setError("Name and company are required.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const created = await createLead({
        name: form.name.trim(),
        company: form.company.trim(),
        website_url: form.website_url.trim() || null,
        email: form.email.trim() || null,
        location: form.location.trim() || null,
        industry: form.industry.trim() || null,
        status: form.status || "new",
        source: form.source || "manual"
      });
      router.push(`/leads/${created.id}`);
    } catch (submitError) {
      setError(getErrorMessage(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Create Lead</h1>
            <p className="page-subtitle">Add a new account to your CRM pipeline.</p>
          </div>
          <Link href="/" className="btn-secondary btn-link">
            Back
          </Link>
        </header>
      </section>

      <section className="stats-grid">
        <div className="metric-card">
          <div className="metric-label">Tip</div>
          <div className="muted">Include a valid `website_url` so Agent 1 can run immediately after ingestion.</div>
        </div>
        <div className="metric-card">
          <div className="metric-label">Pipeline</div>
          <div className="muted">Ingest -&gt; Agent 1 -&gt; Agent 2 -&gt; Agent 3</div>
        </div>
      </section>

      <section className="card stack">
        <form onSubmit={onSubmit} className="stack">
          <div className="row">
            <div className="field">
              <label htmlFor="name">Name *</label>
              <input id="name" value={form.name} onChange={(event) => updateField("name", event.target.value)} required />
            </div>
            <div className="field">
              <label htmlFor="company">Company *</label>
              <input
                id="company"
                value={form.company}
                onChange={(event) => updateField("company", event.target.value)}
                required
              />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label htmlFor="website_url">Website URL</label>
              <input
                id="website_url"
                placeholder="https://example.com"
                value={form.website_url}
                onChange={(event) => updateField("website_url", event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input id="email" value={form.email} onChange={(event) => updateField("email", event.target.value)} />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label htmlFor="location">Location</label>
              <input id="location" value={form.location} onChange={(event) => updateField("location", event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="industry">Industry</label>
              <input id="industry" value={form.industry} onChange={(event) => updateField("industry", event.target.value)} />
            </div>
          </div>

          <div className="row">
            <div className="field">
              <label htmlFor="status">Status</label>
              <input id="status" value={form.status} onChange={(event) => updateField("status", event.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="source">Source</label>
              <input id="source" value={form.source} onChange={(event) => updateField("source", event.target.value)} />
            </div>
          </div>

          {error ? <div className="error">{error}</div> : null}

          <div className="inline-actions">
            <button className="btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Creating..." : "Create Lead"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
