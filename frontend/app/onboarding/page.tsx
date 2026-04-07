"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  generateWorkspaceAiStrategy,
  getWorkspaceAiStrategy,
  getWorkspaceProfile,
  getWorkspaceSettings,
  patchWorkspaceAiStrategy,
  patchWorkspaceProfile,
  patchWorkspaceSettings
} from "@/src/lib/api";
import { WorkspaceAiStrategy } from "@/src/lib/types";

type OnboardingStep = 1 | 2 | 3 | 4;

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleListItem(values: string[], key: string): string[] {
  if (values.includes(key)) return values.filter((v) => v !== key);
  return [...values, key];
}

const STEPS: Array<{ num: OnboardingStep; label: string }> = [
  { num: 1, label: "Your business" },
  { num: 2, label: "Integrations" },
  { num: 3, label: "AI style" },
  { num: 4, label: "Outreach strategy" }
];

export default function OnboardingPage() {
  const router = useRouter();
  const [step, setStep] = useState<OnboardingStep>(1);

  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [industriesServed, setIndustriesServed] = useState("");
  const [serviceSpecialties, setServiceSpecialties] = useState("");
  const [serviceArea, setServiceArea] = useState("");

  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [googleOAuthClientId, setGoogleOAuthClientId] = useState("");
  const [googleOAuthClientSecret, setGoogleOAuthClientSecret] = useState("");
  const [gmailOAuthRedirectUri, setGmailOAuthRedirectUri] = useState("");

  const [preferredTone, setPreferredTone] = useState("");
  const [outreachStyle, setOutreachStyle] = useState("");
  const [preferredCta, setPreferredCta] = useState("");
  const [doNotMention, setDoNotMention] = useState("");

  const [aiStrategy, setAiStrategy] = useState<WorkspaceAiStrategy | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedPainPoints, setSelectedPainPoints] = useState<string[]>([]);
  const [selectedCtaStyle, setSelectedCtaStyle] = useState("");

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    void Promise.all([getWorkspaceProfile(), getWorkspaceSettings(), getWorkspaceAiStrategy()])
      .then(([profile, settings, strategy]) => {
        setBusinessName(profile.business_name ?? "");
        setBusinessDescription(profile.business_description ?? "");
        setIndustriesServed((profile.industries_served ?? []).join(", "));
        setServiceSpecialties((profile.service_specialties ?? []).join(", "));
        setServiceArea(profile.service_area ?? "");
        setOpenaiApiKey(settings.openai_api_key ?? "");
        setGoogleApiKey(settings.google_places_api_key ?? "");
        setGoogleOAuthClientId(settings.google_oauth_client_id ?? "");
        setGoogleOAuthClientSecret(settings.google_oauth_client_secret ?? "");
        setGmailOAuthRedirectUri(settings.gmail_oauth_redirect_uri ?? "");
        setPreferredTone(profile.preferred_tone ?? "");
        setOutreachStyle(profile.outreach_style ?? "");
        setPreferredCta(profile.preferred_cta ?? "");
        setDoNotMention((profile.do_not_mention ?? []).join(", "));
        setAiStrategy(strategy);
        setSelectedCategories(strategy.selected_target_categories ?? []);
        setSelectedPainPoints(strategy.selected_priority_pain_points ?? []);
        setSelectedCtaStyle(strategy.selected_cta_style ?? "");
      })
      .catch((e) => setError(getErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  function applyStrategyState(s: WorkspaceAiStrategy) {
    setAiStrategy(s);
    setSelectedCategories(s.selected_target_categories ?? []);
    setSelectedPainPoints(s.selected_priority_pain_points ?? []);
    setSelectedCtaStyle(s.selected_cta_style ?? "");
  }

  async function onSaveStep1(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await patchWorkspaceProfile({
        business_name: businessName.trim() || null,
        business_description: businessDescription.trim() || null,
        industries_served: csvToList(industriesServed),
        service_specialties: csvToList(serviceSpecialties),
        service_area: serviceArea.trim() || null
      });
      setMessage("Saved.");
      setStep(2);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function onSaveStep2(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await patchWorkspaceSettings({
        openai_api_key: openaiApiKey.trim() || null,
        google_places_api_key: googleApiKey.trim() || null,
        google_oauth_client_id: googleOAuthClientId.trim() || null,
        google_oauth_client_secret: googleOAuthClientSecret.trim() || null,
        gmail_oauth_redirect_uri: gmailOAuthRedirectUri.trim() || null
      });
      setMessage("Saved.");
      setStep(3);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function onSaveStep3(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await patchWorkspaceProfile({
        preferred_tone: preferredTone.trim() || null,
        outreach_style: outreachStyle.trim() || null,
        preferred_cta: preferredCta.trim() || null,
        do_not_mention: csvToList(doNotMention)
      });
      setMessage("Saved.");
      setStep(4);
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  async function onGenerateStrategy() {
    setGenerating(true);
    setError(null);
    setMessage(null);
    try {
      const generated = await generateWorkspaceAiStrategy();
      applyStrategyState(generated);
      setMessage("Strategy generated. Review and save your selections.");
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setGenerating(false);
    }
  }

  async function onSaveStep4(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      await patchWorkspaceAiStrategy({
        selected_target_categories: selectedCategories,
        selected_priority_pain_points: selectedPainPoints,
        selected_cta_style: selectedCtaStyle.trim() || null
      });
      setMessage("Saved.");
    } catch (e) {
      setError(getErrorMessage(e));
    } finally {
      setSaving(false);
    }
  }

  function onFinish() {
    router.push("/");
  }

  const strategyGen = aiStrategy?.generated_strategy;
  const idealCustomers = strategyGen?.ideal_customers ?? [];
  const painPoints = strategyGen?.priority_pain_points ?? [];
  const rapportPoints = strategyGen?.rapport_points ?? [];
  const ctas = strategyGen?.cta_recommendations ?? [];

  if (loading) {
    return (
      <div className="onboarding-page">
        <div className="onboarding-loading">
          <span className="muted">Loading...</span>
        </div>
      </div>
    );
  }

  if (error && !businessName && !industriesServed) {
    return (
      <div className="onboarding-page">
        <div className="onboarding-card">
          <h2>Setup required</h2>
          <p className="muted">Please log in first to configure your workspace.</p>
          <div className="error" style={{ marginTop: 16 }}>{error}</div>
          <div className="onboarding-actions" style={{ marginTop: 20 }}>
            <Link href="/login" className="btn-primary btn-link">Go to login</Link>
            <Link href="/" className="btn-secondary btn-link">Back to dashboard</Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="onboarding-page">
      <div className="onboarding-header">
        <Link href="/" className="onboarding-brand">
          <span className="brand">CRM Command</span>
        </Link>
        <span className="onboarding-title">Get started</span>
      </div>

      <div className="onboarding-stepper">
        {STEPS.map((s) => (
          <div
            key={s.num}
            className={`onboarding-step-dot ${step === s.num ? "active" : step > s.num ? "done" : "pending"}`}
            onClick={() => setStep(s.num)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => e.key === "Enter" && setStep(s.num)}
            aria-label={`Step ${s.num}: ${s.label}`}
          >
            <span className="step-num">{s.num}</span>
          </div>
        ))}
      </div>
      <div className="onboarding-step-labels">
        {STEPS.map((s) => (
          <span key={s.num} className={step === s.num ? "active" : ""}>
            {s.label}
          </span>
        ))}
      </div>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="success">{message}</div> : null}

      <div className="onboarding-card">
        {step === 1 && (
          <form className="stack" onSubmit={onSaveStep1}>
            <h2>Tell us about your business</h2>
            <p className="muted">This helps us tailor outreach and AI-generated content.</p>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_business_name">Business name</label>
                <input
                  id="ob_business_name"
                  value={businessName}
                  onChange={(e) => setBusinessName(e.target.value)}
                  placeholder="Acme Services"
                />
              </div>
              <div className="field">
                <label htmlFor="ob_service_area">Service area</label>
                <input
                  id="ob_service_area"
                  value={serviceArea}
                  onChange={(e) => setServiceArea(e.target.value)}
                  placeholder="Northern California"
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="ob_description">What do you do?</label>
              <textarea
                id="ob_description"
                value={businessDescription}
                onChange={(e) => setBusinessDescription(e.target.value)}
                placeholder="Managed IT for restaurants and hospitality. Wi-Fi, POS, cameras."
                rows={3}
              />
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_industries">Industries you serve (comma-separated)</label>
                <input
                  id="ob_industries"
                  value={industriesServed}
                  onChange={(e) => setIndustriesServed(e.target.value)}
                  placeholder="restaurants, hospitality, retail"
                />
              </div>
              <div className="field">
                <label htmlFor="ob_specialties">Service specialties (comma-separated)</label>
                <input
                  id="ob_specialties"
                  value={serviceSpecialties}
                  onChange={(e) => setServiceSpecialties(e.target.value)}
                  placeholder="wifi, POS, cameras"
                />
              </div>
            </div>
            <div className="onboarding-actions">
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Saving..." : "Continue"}
              </button>
              <Link href="/" className="btn-secondary btn-link">
                Skip for now
              </Link>
            </div>
          </form>
        )}

        {step === 2 && (
          <form className="stack" onSubmit={onSaveStep2}>
            <h2>Integrations</h2>
            <p className="muted">Add your API keys to enable AI features, prospect search, and Gmail connect.</p>
            <div className="field">
              <label htmlFor="ob_openai">OpenAI API key</label>
              <input
                id="ob_openai"
                type="password"
                placeholder="sk-..."
                value={openaiApiKey}
                onChange={(e) => setOpenaiApiKey(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="ob_google">Google Places API key (optional)</label>
              <input
                id="ob_google"
                type="password"
                placeholder="AIza..."
                value={googleApiKey}
                onChange={(e) => setGoogleApiKey(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="ob_gmail_client_id">Gmail: Google OAuth Client ID (optional)</label>
              <input
                id="ob_gmail_client_id"
                type="text"
                autoComplete="off"
                placeholder="xxx.apps.googleusercontent.com"
                value={googleOAuthClientId}
                onChange={(e) => setGoogleOAuthClientId(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="ob_gmail_secret">Gmail: OAuth Client Secret (optional)</label>
              <input
                id="ob_gmail_secret"
                type="password"
                autoComplete="new-password"
                placeholder="GOCSPX-..."
                value={googleOAuthClientSecret}
                onChange={(e) => setGoogleOAuthClientSecret(e.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="ob_gmail_redirect">Gmail: redirect URI (optional)</label>
              <input
                id="ob_gmail_redirect"
                type="url"
                autoComplete="off"
                placeholder="http://localhost:8000/api/v1/integrations/gmail/callback"
                value={gmailOAuthRedirectUri}
                onChange={(e) => setGmailOAuthRedirectUri(e.target.value)}
              />
            </div>
            <div className="onboarding-actions">
              <button type="button" className="btn-secondary" onClick={() => setStep(1)}>
                Back
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Saving..." : "Continue"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setStep(4)}>
                Skip
              </button>
            </div>
          </form>
        )}

        {step === 3 && (
          <form className="stack" onSubmit={onSaveStep3}>
            <h2>AI outreach style</h2>
            <p className="muted">How should Agent 2 write your outreach emails?</p>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_tone">Tone</label>
                <input
                  id="ob_tone"
                  value={preferredTone}
                  onChange={(e) => setPreferredTone(e.target.value)}
                  placeholder="professional, warm"
                />
              </div>
              <div className="field">
                <label htmlFor="ob_style">Outreach style</label>
                <input
                  id="ob_style"
                  value={outreachStyle}
                  onChange={(e) => setOutreachStyle(e.target.value)}
                  placeholder="consultative"
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="ob_cta">Default call-to-action</label>
              <textarea
                id="ob_cta"
                value={preferredCta}
                onChange={(e) => setPreferredCta(e.target.value)}
                placeholder="Would you be open to a 15-minute call?"
                rows={2}
              />
            </div>
            <div className="field">
              <label htmlFor="ob_avoid">Things to avoid (comma-separated)</label>
              <input
                id="ob_avoid"
                value={doNotMention}
                onChange={(e) => setDoNotMention(e.target.value)}
                placeholder="pricing guarantees, competitor names"
              />
            </div>
            <div className="onboarding-actions">
              <button type="button" className="btn-secondary" onClick={() => setStep(2)}>
                Back
              </button>
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? "Saving..." : "Continue"}
              </button>
              <button type="button" className="btn-secondary" onClick={() => setStep(4)}>
                Skip
              </button>
            </div>
          </form>
        )}

        {step === 4 && (
          <div className="stack">
            <h2>Outreach strategy</h2>
            <p className="muted">
              Generate AI-suggested target categories and pain points. Select which ones Agent 2 should use.
            </p>

            {!strategyGen ? (
              <div className="onboarding-strategy-empty">
                <p>No strategy generated yet. Click below to generate suggestions from your profile.</p>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void onGenerateStrategy()}
                  disabled={generating}
                >
                  {generating ? "Generating..." : "Generate strategy"}
                </button>
              </div>
            ) : (
              <form className="stack" onSubmit={onSaveStep4}>
                <div className="kv">
                  <strong>Core positioning</strong>
                  {strategyGen.core_positioning || "—"}
                </div>

                <div className="row">
                  <div className="field">
                    <label>Target categories</label>
                    <div className="stack">
                      {idealCustomers.map((item) => (
                        <label key={item.category} className="onboarding-check">
                          <input
                            type="checkbox"
                            checked={selectedCategories.includes(item.category)}
                            onChange={() => setSelectedCategories((p) => toggleListItem(p, item.category))}
                          />
                          <span><strong>{item.display_name}</strong> — {item.why_fit}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="field">
                    <label>Pain points</label>
                    <div className="stack">
                      {painPoints.map((item) => (
                        <label key={item.key} className="onboarding-check">
                          <input
                            type="checkbox"
                            checked={selectedPainPoints.includes(item.key)}
                            onChange={() => setSelectedPainPoints((p) => toggleListItem(p, item.key))}
                          />
                          <span><strong>{item.label}</strong> — {item.why_relevant}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                {rapportPoints.length > 0 && (
                  <div className="field">
                    <label>Rapport hooks (Agent 2 uses these to open emails)</label>
                    <div className="stack">
                      {rapportPoints.map((item) => (
                        <div key={item.category} className="kv">
                          <strong>{item.display_name}</strong>
                          <span className="muted">{item.hooks.join(" • ")}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="field">
                  <label htmlFor="ob_cta_style">Preferred CTA</label>
                  <select
                    id="ob_cta_style"
                    value={selectedCtaStyle}
                    onChange={(e) => setSelectedCtaStyle(e.target.value)}
                  >
                    <option value="">No preference</option>
                    {ctas.map((c) => (
                      <option key={c.key} value={c.key}>{c.label}</option>
                    ))}
                  </select>
                </div>

                <div className="onboarding-actions">
                  <button type="button" className="btn-secondary" onClick={() => setStep(3)}>
                    Back
                  </button>
                  <button type="button" className="btn-secondary" onClick={() => void onGenerateStrategy()} disabled={generating}>
                    Regenerate
                  </button>
                  <button type="submit" className="btn-secondary" disabled={saving}>
                    {saving ? "Saving..." : "Save selections"}
                  </button>
                  <button type="button" className="btn-primary" onClick={onFinish}>
                    Go to dashboard
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>

      <div className="onboarding-footer">
        <Link href="/settings">Advanced settings</Link>
        <span className="muted">·</span>
        <Link href="/">Skip setup</Link>
      </div>
    </div>
  );
}
