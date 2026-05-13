"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  generateWorkspaceAiStrategy,
  getApiBase,
  getGmailConnectUrl,
  getGmailStatus,
  getWorkspaceAiStrategy,
  getWorkspaceProfile,
  getWorkspaceSettings,
  patchWorkspaceAiStrategy,
  patchWorkspaceProfile,
  patchWorkspaceSettings,
} from "@/src/lib/api";
import { WorkspaceAiStrategy } from "@/src/lib/types";

type OnboardingStep = 1 | 2 | 3 | 4 | 5;

const STEPS: Array<{ num: OnboardingStep; label: string }> = [
  { num: 1, label: "About you" },
  { num: 2, label: "API keys" },
  { num: 3, label: "Gmail" },
  { num: 4, label: "AI style" },
  { num: 5, label: "Strategy" },
];

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
}

function csvToList(value: string): string[] {
  return value.split(",").map((s) => s.trim()).filter(Boolean);
}

function toggleListItem(values: string[], key: string): string[] {
  return values.includes(key) ? values.filter((v) => v !== key) : [...values, key];
}

function HelpLink({ href, children, style }: { href: string; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="ob-help-link" style={style}>
      {children} ↗
    </a>
  );
}

export default function OnboardingPage() {
  const router = useRouter();

  const [step, setStep] = useState<OnboardingStep>(1);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  // Step 1 — About you
  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [serviceArea, setServiceArea] = useState("");
  const [industriesServed, setIndustriesServed] = useState("");
  const [serviceSpecialties, setServiceSpecialties] = useState("");
  const [senderName, setSenderName] = useState("");
  const [senderTitle, setSenderTitle] = useState("");
  const [senderPhone, setSenderPhone] = useState("");
  const [senderEmail, setSenderEmail] = useState("");

  // Step 2 — API keys
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [anthropicApiKey, setAnthropicApiKey] = useState("");
  const [googleApiKey, setGoogleApiKey] = useState("");

  // Step 3 — Gmail / Google OAuth
  const [googleOAuthClientId, setGoogleOAuthClientId] = useState("");
  const [googleOAuthClientSecret, setGoogleOAuthClientSecret] = useState("");
  const [gmailOAuthRedirectUri, setGmailOAuthRedirectUri] = useState("");
  const [gmailConnected, setGmailConnected] = useState(false);
  const [gmailEmail, setGmailEmail] = useState<string | null>(null);
  const [connectingGmail, setConnectingGmail] = useState(false);

  // Step 4 — AI style
  const [preferredTone, setPreferredTone] = useState("");
  const [outreachStyle, setOutreachStyle] = useState("");
  const [preferredCta, setPreferredCta] = useState("");
  const [doNotMention, setDoNotMention] = useState("");

  // Step 5 — Strategy
  const [aiStrategy, setAiStrategy] = useState<WorkspaceAiStrategy | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedPainPoints, setSelectedPainPoints] = useState<string[]>([]);
  const [selectedCtaStyle, setSelectedCtaStyle] = useState("");

  useEffect(() => {
    setLoading(true);
    void Promise.all([getWorkspaceProfile(), getWorkspaceSettings(), getWorkspaceAiStrategy(), getGmailStatus()])
      .then(([profile, settings, strategy, gmailStatus]) => {
        setBusinessName(profile.business_name ?? "");
        setBusinessDescription(profile.business_description ?? "");
        setServiceArea(profile.service_area ?? "");
        setIndustriesServed((profile.industries_served ?? []).join(", "));
        setServiceSpecialties((profile.service_specialties ?? []).join(", "));
        setSenderName(profile.sender_name ?? "");
        setSenderTitle(profile.sender_title ?? "");
        setSenderPhone(profile.sender_phone ?? "");
        setSenderEmail(profile.sender_email ?? "");

        setOpenaiApiKey(settings.openai_api_key ?? "");
        setAnthropicApiKey(settings.anthropic_api_key ?? "");
        setGoogleApiKey(settings.google_places_api_key ?? "");
        setGoogleOAuthClientId(settings.google_oauth_client_id ?? "");
        setGoogleOAuthClientSecret(settings.google_oauth_client_secret ?? "");
        setGmailOAuthRedirectUri(settings.gmail_oauth_redirect_uri ?? "");

        setGmailConnected(gmailStatus.connected);
        setGmailEmail(gmailStatus.connected_email ?? null);

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

  function clearMessages() {
    setError(null);
    setMessage(null);
  }

  // ── Step handlers ──────────────────────────────────────────────────────────

  async function onSaveStep1(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    clearMessages();
    try {
      await patchWorkspaceProfile({
        business_name: businessName.trim() || null,
        business_description: businessDescription.trim() || null,
        service_area: serviceArea.trim() || null,
        industries_served: csvToList(industriesServed),
        service_specialties: csvToList(serviceSpecialties),
        sender_name: senderName.trim() || null,
        sender_title: senderTitle.trim() || null,
        sender_phone: senderPhone.trim() || null,
        sender_email: senderEmail.trim() || null,
      });
      setStep(2);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function onSaveStep2(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    clearMessages();
    try {
      await patchWorkspaceSettings({
        openai_api_key: openaiApiKey.trim() || null,
        anthropic_api_key: anthropicApiKey.trim() || null,
        google_places_api_key: googleApiKey.trim() || null,
      });
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function onSaveStep3Credentials(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    clearMessages();
    try {
      await patchWorkspaceSettings({
        google_oauth_client_id: googleOAuthClientId.trim() || null,
        google_oauth_client_secret: googleOAuthClientSecret.trim() || null,
        gmail_oauth_redirect_uri: gmailOAuthRedirectUri.trim() || null,
      });
      setMessage("OAuth credentials saved.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function onConnectGmail() {
    setConnectingGmail(true);
    clearMessages();
    try {
      const { connect_url } = await getGmailConnectUrl();
      if (!connect_url.startsWith("https://")) throw new Error("Invalid OAuth URL.");
      window.location.href = connect_url;
    } catch (err) {
      setError(getErrorMessage(err));
      setConnectingGmail(false);
    }
  }

  async function onSaveStep4(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    clearMessages();
    try {
      await patchWorkspaceProfile({
        preferred_tone: preferredTone.trim() || null,
        outreach_style: outreachStyle.trim() || null,
        preferred_cta: preferredCta.trim() || null,
        do_not_mention: csvToList(doNotMention),
      });
      setStep(5);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  async function onGenerateStrategy() {
    setGenerating(true);
    clearMessages();
    try {
      const generated = await generateWorkspaceAiStrategy();
      applyStrategyState(generated);
      setMessage("Strategy generated — review and save your selections.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setGenerating(false);
    }
  }

  async function onSaveStep5(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setSaving(true);
    clearMessages();
    try {
      await patchWorkspaceAiStrategy({
        selected_target_categories: selectedCategories,
        selected_priority_pain_points: selectedPainPoints,
        selected_cta_style: selectedCtaStyle.trim() || null,
      });
      router.push("/");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  const strategyGen = aiStrategy?.generated_strategy;
  const idealCustomers = strategyGen?.ideal_customers ?? [];
  const painPoints = strategyGen?.priority_pain_points ?? [];
  const ctas = strategyGen?.cta_recommendations ?? [];

  if (loading) {
    return (
      <div className="onboarding-page">
        <div className="onboarding-loading"><span className="muted">Loading…</span></div>
      </div>
    );
  }

  return (
    <div className="onboarding-page">
      {/* Header */}
      <div className="onboarding-header">
        <Link href="/" className="onboarding-brand">
          <span className="brand">CRM <span style={{ color: "var(--blue)" }}>Command</span></span>
        </Link>
        <span className="onboarding-title">Let&apos;s get you set up</span>
      </div>

      {/* Stepper */}
      <div className="onboarding-stepper">
        {STEPS.map((s) => (
          <div
            key={s.num}
            className={`onboarding-step-dot ${step === s.num ? "active" : step > s.num ? "done" : "pending"}`}
            onClick={() => s.num < step && setStep(s.num)}
            role={s.num < step ? "button" : undefined}
            tabIndex={s.num < step ? 0 : undefined}
            onKeyDown={(e) => e.key === "Enter" && s.num < step && setStep(s.num)}
            aria-label={`Step ${s.num}: ${s.label}`}
          >
            {step > s.num ? "✓" : <span className="step-num">{s.num}</span>}
          </div>
        ))}
      </div>
      <div className="onboarding-step-labels">
        {STEPS.map((s) => (
          <span key={s.num} className={step === s.num ? "active" : ""}>{s.label}</span>
        ))}
      </div>

      {/* Feedback */}
      {error ? <div className="error" style={{ maxWidth: 640, margin: "0 auto 8px" }}>{error}</div> : null}
      {message ? <div className="success" style={{ maxWidth: 640, margin: "0 auto 8px" }}>{message}</div> : null}

      {/* Card */}
      <div className="onboarding-card">

        {/* ── Step 1: About you ── */}
        {step === 1 && (
          <form className="stack" onSubmit={onSaveStep1}>
            <div className="ob-step-header">
              <h2>Tell us about your business</h2>
              <p className="muted">This powers AI-generated outreach and personalises every email.</p>
            </div>

            <div className="ob-section-label">Business details</div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_bname">Business name</label>
                <input id="ob_bname" value={businessName} onChange={(e) => setBusinessName(e.target.value)} placeholder="Acme Managed IT" />
              </div>
              <div className="field">
                <label htmlFor="ob_area">Service area</label>
                <input id="ob_area" value={serviceArea} onChange={(e) => setServiceArea(e.target.value)} placeholder="Northern California" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="ob_desc">What do you do?</label>
              <textarea id="ob_desc" rows={3} value={businessDescription} onChange={(e) => setBusinessDescription(e.target.value)} placeholder="Managed IT for restaurants and hotels — Wi-Fi, POS networking, camera systems." />
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_ind">Industries served <span className="muted">(comma-separated)</span></label>
                <input id="ob_ind" value={industriesServed} onChange={(e) => setIndustriesServed(e.target.value)} placeholder="restaurants, hospitality, retail" />
              </div>
              <div className="field">
                <label htmlFor="ob_spec">Service specialties <span className="muted">(comma-separated)</span></label>
                <input id="ob_spec" value={serviceSpecialties} onChange={(e) => setServiceSpecialties(e.target.value)} placeholder="wifi, POS, cameras" />
              </div>
            </div>

            <div className="ob-section-label" style={{ marginTop: 12 }}>
              Your contact info
              <span className="muted" style={{ fontWeight: 400, marginLeft: 8 }}>Used in email signatures — without these AI emails will have placeholder brackets</span>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_sname">Your name</label>
                <input id="ob_sname" value={senderName} onChange={(e) => setSenderName(e.target.value)} placeholder="John Smith" />
              </div>
              <div className="field">
                <label htmlFor="ob_stitle">Your title</label>
                <input id="ob_stitle" value={senderTitle} onChange={(e) => setSenderTitle(e.target.value)} placeholder="Owner / Account Executive" />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_sphone">Phone number</label>
                <input id="ob_sphone" type="tel" value={senderPhone} onChange={(e) => setSenderPhone(e.target.value)} placeholder="(555) 123-4567" />
              </div>
              <div className="field">
                <label htmlFor="ob_semail">Your email</label>
                <input id="ob_semail" type="email" value={senderEmail} onChange={(e) => setSenderEmail(e.target.value)} placeholder="john@yourcompany.com" />
              </div>
            </div>

            <div className="onboarding-actions">
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Saving…" : "Continue →"}</button>
              <Link href="/" className="btn-secondary btn-link">Skip setup</Link>
            </div>
          </form>
        )}

        {/* ── Step 2: API Keys ── */}
        {step === 2 && (
          <form className="stack" onSubmit={onSaveStep2}>
            <div className="ob-step-header">
              <h2>API Keys</h2>
              <p className="muted">Connect the services that power CRM Command&apos;s AI and prospecting features.</p>
            </div>

            {/* Anthropic */}
            <div className="ob-key-block">
              <div className="ob-key-header">
                <strong>Anthropic API Key</strong>
                <span className="ob-required-badge">Recommended for emails</span>
              </div>
              <p className="muted ob-key-desc">
                Used for outreach email generation — Claude follows nuanced instructions more reliably than GPT.{" "}
                <HelpLink href="https://console.anthropic.com/settings/keys">Get your key at console.anthropic.com</HelpLink>
              </p>
              <input
                type="password"
                placeholder="sk-ant-..."
                value={anthropicApiKey}
                onChange={(e) => setAnthropicApiKey(e.target.value)}
                autoComplete="off"
              />
            </div>

            {/* OpenAI */}
            <div className="ob-key-block">
              <div className="ob-key-header">
                <strong>OpenAI API Key</strong>
                <span className="ob-optional-badge">Used if no Anthropic key</span>
              </div>
              <p className="muted ob-key-desc">
                Used for lead scoring, AI strategy, and email generation as a fallback.{" "}
                <HelpLink href="https://platform.openai.com/api-keys">Get your key at platform.openai.com</HelpLink>
              </p>
              <input
                type="password"
                placeholder="sk-..."
                value={openaiApiKey}
                onChange={(e) => setOpenaiApiKey(e.target.value)}
                autoComplete="off"
              />
            </div>

            {/* Google Places */}
            <div className="ob-key-block">
              <div className="ob-key-header">
                <strong>Google Places API Key</strong>
                <span className="ob-optional-badge">Optional</span>
              </div>
              <p className="muted ob-key-desc">
                Used for prospect discovery — finds businesses near your service area.{" "}
                <HelpLink href="https://console.cloud.google.com/apis/library/places-backend.googleapis.com">Enable Places API in Google Cloud Console</HelpLink>
              </p>
              <input
                type="password"
                placeholder="AIza..."
                value={googleApiKey}
                onChange={(e) => setGoogleApiKey(e.target.value)}
                autoComplete="off"
              />
            </div>

            <div className="onboarding-actions">
              <button type="button" className="btn-secondary" onClick={() => setStep(1)}>← Back</button>
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Saving…" : "Continue →"}</button>
              <button type="button" className="btn-secondary" onClick={() => setStep(3)}>Skip</button>
            </div>
          </form>
        )}

        {/* ── Step 3: Gmail ── */}
        {step === 3 && (
          <div className="stack">
            <div className="ob-step-header">
              <h2>Connect Gmail</h2>
              <p className="muted">Send outreach emails directly through your Gmail account. Replies sync back automatically.</p>
            </div>

            {gmailConnected ? (
              <div className="ob-gmail-connected">
                <span className="ob-connected-dot">●</span>
                <div>
                  <strong>Gmail connected</strong>
                  <div className="muted" style={{ fontSize: ".83rem" }}>{gmailEmail}</div>
                </div>
              </div>
            ) : (
              <>
                {/* Sub-step A: OAuth credentials */}
                <form className="stack" onSubmit={onSaveStep3Credentials}>
                  <div className="ob-section-label">
                    Step 1 — Add your Google OAuth credentials
                    <HelpLink href="https://console.cloud.google.com/apis/credentials" style={{ marginLeft: 8 }}>
                      Open Google Cloud Console
                    </HelpLink>
                  </div>
                  <div className="ob-callout">
                    <ol className="ob-setup-steps">
                      <li>Go to <strong>APIs &amp; Services → Credentials</strong> in Google Cloud Console</li>
                      <li>Click <strong>Create Credentials → OAuth 2.0 Client ID</strong>, choose <strong>Web application</strong></li>
                      <li>Under <strong>Authorized redirect URIs</strong>, add both:
                        <div className="ob-uri-list">
                          <code>http://localhost:8000/api/v1/auth/google/callback</code>
                          <code>http://localhost:8000/api/v1/integrations/gmail/callback</code>
                        </div>
                      </li>
                      <li>Copy the <strong>Client ID</strong> and <strong>Client secret</strong> below</li>
                    </ol>
                  </div>
                  <div className="row">
                    <div className="field">
                      <label htmlFor="ob_gcid">Google OAuth Client ID</label>
                      <input id="ob_gcid" type="text" autoComplete="off" placeholder="xxx.apps.googleusercontent.com" value={googleOAuthClientId} onChange={(e) => setGoogleOAuthClientId(e.target.value)} />
                    </div>
                    <div className="field">
                      <label htmlFor="ob_gcs">OAuth Client Secret</label>
                      <input id="ob_gcs" type="password" autoComplete="new-password" placeholder="GOCSPX-..." value={googleOAuthClientSecret} onChange={(e) => setGoogleOAuthClientSecret(e.target.value)} />
                    </div>
                  </div>
                  <div className="field">
                    <label htmlFor="ob_redirect">Redirect URI override <span className="muted">(leave blank to use default)</span></label>
                    <input id="ob_redirect" type="url" autoComplete="off" placeholder="http://localhost:8000/api/v1/integrations/gmail/callback" value={gmailOAuthRedirectUri} onChange={(e) => setGmailOAuthRedirectUri(e.target.value)} />
                  </div>
                  <div>
                    <button type="submit" className="btn-secondary" disabled={saving} style={{ fontSize: ".85rem" }}>
                      {saving ? "Saving…" : "Save credentials"}
                    </button>
                  </div>
                </form>

                {/* Sub-step B: Connect Gmail */}
                <div className="ob-section-label" style={{ marginTop: 8 }}>Step 2 — Sign in to Gmail</div>
                <button
                  type="button"
                  className="ob-gmail-btn"
                  disabled={connectingGmail || (!googleOAuthClientId && !googleOAuthClientSecret)}
                  title={!googleOAuthClientId ? "Save your OAuth credentials first" : undefined}
                  onClick={() => void onConnectGmail()}
                >
                  <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
                    <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"/>
                    <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.18l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"/>
                    <path fill="#FBBC05" d="M3.964 10.71A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.71V4.958H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.042l3.007-2.332Z"/>
                    <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.958L3.964 7.29C4.672 5.163 6.656 3.58 9 3.58Z"/>
                  </svg>
                  {connectingGmail ? "Redirecting to Google…" : "Connect Gmail account"}
                </button>
              </>
            )}

            <div className="onboarding-actions" style={{ marginTop: 16 }}>
              <button type="button" className="btn-secondary" onClick={() => setStep(2)}>← Back</button>
              <button type="button" className="btn-primary" onClick={() => setStep(4)}>
                {gmailConnected ? "Continue →" : "Skip for now →"}
              </button>
            </div>
          </div>
        )}

        {/* ── Step 4: AI Style ── */}
        {step === 4 && (
          <form className="stack" onSubmit={onSaveStep4}>
            <div className="ob-step-header">
              <h2>AI outreach style</h2>
              <p className="muted">How should the AI write emails on your behalf?</p>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="ob_tone">Tone</label>
                <input id="ob_tone" value={preferredTone} onChange={(e) => setPreferredTone(e.target.value)} placeholder="professional, warm, direct" />
              </div>
              <div className="field">
                <label htmlFor="ob_style">Outreach style</label>
                <input id="ob_style" value={outreachStyle} onChange={(e) => setOutreachStyle(e.target.value)} placeholder="consultative, value-led" />
              </div>
            </div>
            <div className="field">
              <label htmlFor="ob_cta">Default call-to-action</label>
              <textarea id="ob_cta" rows={2} value={preferredCta} onChange={(e) => setPreferredCta(e.target.value)} placeholder="Would you be open to a 15-minute call this week?" />
            </div>
            <div className="field">
              <label htmlFor="ob_avoid">Things to avoid <span className="muted">(comma-separated)</span></label>
              <input id="ob_avoid" value={doNotMention} onChange={(e) => setDoNotMention(e.target.value)} placeholder="pricing guarantees, competitor names, discounts" />
            </div>
            <div className="onboarding-actions">
              <button type="button" className="btn-secondary" onClick={() => setStep(3)}>← Back</button>
              <button type="submit" className="btn-primary" disabled={saving}>{saving ? "Saving…" : "Continue →"}</button>
              <button type="button" className="btn-secondary" onClick={() => setStep(5)}>Skip</button>
            </div>
          </form>
        )}

        {/* ── Step 5: Strategy ── */}
        {step === 5 && (
          <div className="stack">
            <div className="ob-step-header">
              <h2>AI outreach strategy <span className="ob-optional-badge" style={{ fontSize: ".75rem", verticalAlign: "middle" }}>Optional</span></h2>
              <p className="muted">Generate AI-suggested target categories and pain points. You can always do this later in Settings.</p>
            </div>

            {!strategyGen ? (
              <div className="onboarding-strategy-empty">
                <p className="muted">No strategy generated yet. This uses your business profile to suggest ideal customer types and pain points for outreach.</p>
                <button type="button" className="btn-primary" onClick={() => void onGenerateStrategy()} disabled={generating}>
                  {generating ? "Generating…" : "Generate strategy"}
                </button>
              </div>
            ) : (
              <form className="stack" onSubmit={onSaveStep5}>
                {strategyGen.core_positioning && (
                  <div className="kv"><strong>Core positioning</strong>{strategyGen.core_positioning}</div>
                )}
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
                <div className="field">
                  <label htmlFor="ob_cta_style">Preferred CTA style</label>
                  <select id="ob_cta_style" value={selectedCtaStyle} onChange={(e) => setSelectedCtaStyle(e.target.value)}>
                    <option value="">No preference</option>
                    {ctas.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
                  </select>
                </div>
                <div className="onboarding-actions">
                  <button type="button" className="btn-secondary" onClick={() => setStep(4)}>← Back</button>
                  <button type="button" className="btn-secondary" onClick={() => void onGenerateStrategy()} disabled={generating}>
                    {generating ? "Generating…" : "Regenerate"}
                  </button>
                  <button type="submit" className="btn-primary" disabled={saving}>
                    {saving ? "Saving…" : "Save & go to dashboard →"}
                  </button>
                </div>
              </form>
            )}

            {!strategyGen && (
              <div className="onboarding-actions" style={{ marginTop: 12 }}>
                <button type="button" className="btn-secondary" onClick={() => setStep(4)}>← Back</button>
                <button type="button" className="btn-primary" onClick={() => router.push("/")}>Go to dashboard →</button>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="onboarding-footer">
        <Link href="/settings">Advanced settings</Link>
        <span className="muted">·</span>
        <Link href="/">Skip to dashboard</Link>
      </div>
    </div>
  );
}
