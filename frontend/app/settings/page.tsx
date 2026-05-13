"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  ApiError,
  disconnectGmail,
  getApiBaseForDisplay,
  generateWorkspaceAiStrategy,
  getDbExportUrl,
  getGmailConnectUrl,
  getGmailSendAsAliases,
  getGmailStatus,
  getWorkspaceAiStrategy,
  getWorkspaceProfile,
  getWorkspaceSettings,
  importDatabase,
  patchWorkspaceAiStrategy,
  patchWorkspaceProfile,
  patchWorkspaceSettings
} from "@/src/lib/api";
import { SendAsAlias, WorkspaceAiStrategy } from "@/src/lib/types";
import { getUserId, getWorkspaceId, setUserId, setWorkspaceId } from "@/src/lib/identity";

type SettingsTab = "general" | "integrations" | "ai";

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Unexpected error";
}

function csvToList(value: string): string[] {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toggleListItem(values: string[], key: string): string[] {
  if (values.includes(key)) {
    return values.filter((value) => value !== key);
  }
  return [...values, key];
}

function inferPainMatchesSpecialties(label: string, whyRelevant: string, specialties: string[]): string[] {
  if (specialties.length === 0) {
    return [];
  }
  const text = `${label} ${whyRelevant}`.toLowerCase();
  return specialties.filter((specialty) => {
    const specialtyTokens = specialty
      .toLowerCase()
      .split(/[^a-z0-9]+/g)
      .map((token) => token.trim())
      .filter((token) => token.length > 2);
    return specialtyTokens.some((token) => text.includes(token));
  });
}

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [workspaceId, setWorkspaceInput] = useState("");
  const [userId, setUserInput] = useState("");

  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [anthropicApiKey, setAnthropicApiKey] = useState("");
  const [preferredAiProvider, setPreferredAiProvider] = useState("auto");
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [googleOAuthClientId, setGoogleOAuthClientId] = useState("");
  const [googleOAuthClientSecret, setGoogleOAuthClientSecret] = useState("");
  const [gmailOAuthRedirectUri, setGmailOAuthRedirectUri] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [industriesServed, setIndustriesServed] = useState("");
  const [serviceSpecialties, setServiceSpecialties] = useState("");
  const [serviceArea, setServiceArea] = useState("");
  const [preferredTone, setPreferredTone] = useState("");
  const [outreachStyle, setOutreachStyle] = useState("");
  const [preferredCta, setPreferredCta] = useState("");
  const [doNotMention, setDoNotMention] = useState("");
  const [senderName, setSenderName] = useState("");
  const [senderTitle, setSenderTitle] = useState("");
  const [senderPhone, setSenderPhone] = useState("");
  const [senderEmail, setSenderEmail] = useState("");
  const [aiStrategy, setAiStrategy] = useState<WorkspaceAiStrategy | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedPainPoints, setSelectedPainPoints] = useState<string[]>([]);
  const [selectedCtaStyle, setSelectedCtaStyle] = useState("");

  const [identityMessage, setIdentityMessage] = useState<string | null>(null);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [strategyMessage, setStrategyMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);
  const [generatingStrategy, setGeneratingStrategy] = useState(false);
  const [savingStrategy, setSavingStrategy] = useState(false);
  const [importingDb, setImportingDb] = useState(false);
  const [dbImportMessage, setDbImportMessage] = useState<string | null>(null);
  const [dbImportError, setDbImportError] = useState<string | null>(null);

  // Gmail integration
  const [gmailConnected, setGmailConnected] = useState(false);
  const [gmailEmail, setGmailEmail] = useState<string | null>(null);
  const [gmailError, setGmailError] = useState<string | null>(null);
  const [gmailSendAsEmail, setGmailSendAsEmail] = useState("");
  const [gmailSendAsDisplayName, setGmailSendAsDisplayName] = useState("");
  const [gmailAliases, setGmailAliases] = useState<SendAsAlias[]>([]);
  const [connectingGmail, setConnectingGmail] = useState(false);
  const [disconnectingGmail, setDisconnectingGmail] = useState(false);
  const [savingGmailAlias, setSavingGmailAlias] = useState(false);
  const [gmailMessage, setGmailMessage] = useState<string | null>(null);

  function applyAiStrategyState(strategy: WorkspaceAiStrategy): void {
    setAiStrategy(strategy);
    setSelectedCategories(strategy.selected_target_categories ?? []);
    setSelectedPainPoints(strategy.selected_priority_pain_points ?? []);
    setSelectedCtaStyle(strategy.selected_cta_style ?? "");
  }

  useEffect(() => {
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setLoading(true);
    setError(null);
    void Promise.all([getWorkspaceSettings(), getWorkspaceProfile(), getWorkspaceAiStrategy(), getGmailStatus()])
      .then(([settings, profile, strategy, gmailStatus]) => {
        setOpenaiApiKey(settings.openai_api_key ?? "");
        setAnthropicApiKey(settings.anthropic_api_key ?? "");
        setPreferredAiProvider(settings.preferred_ai_provider ?? "auto");
        setGoogleApiKey(settings.google_places_api_key ?? "");
        setGoogleOAuthClientId(settings.google_oauth_client_id ?? "");
        setGoogleOAuthClientSecret(settings.google_oauth_client_secret ?? "");
        setGmailOAuthRedirectUri(settings.gmail_oauth_redirect_uri ?? "");
        setGmailSendAsEmail(settings.gmail_send_as_email ?? "");
        setGmailSendAsDisplayName(settings.gmail_send_as_display_name ?? "");

        setGmailConnected(gmailStatus.connected);
        setGmailEmail(gmailStatus.connected_email ?? null);
        setGmailError(gmailStatus.last_error ?? null);

        if (gmailStatus.connected) {
          void getGmailSendAsAliases().then((r) => setGmailAliases(r.aliases)).catch(() => {});
        }

        setBusinessName(profile.business_name ?? "");
        setBusinessDescription(profile.business_description ?? "");
        setIndustriesServed((profile.industries_served ?? []).join(", "));
        setServiceSpecialties((profile.service_specialties ?? []).join(", "));
        setServiceArea(profile.service_area ?? "");
        setPreferredTone(profile.preferred_tone ?? "");
        setOutreachStyle(profile.outreach_style ?? "");
        setPreferredCta(profile.preferred_cta ?? "");
        setDoNotMention((profile.do_not_mention ?? []).join(", "));
        setSenderName(profile.sender_name ?? "");
        setSenderTitle(profile.sender_title ?? "");
        setSenderPhone(profile.sender_phone ?? "");
        setSenderEmail(profile.sender_email ?? "");

        applyAiStrategyState(strategy);
      })
      .catch((loadError) => setError(getErrorMessage(loadError)))
      .finally(() => setLoading(false));
  }, []);

  function onSaveIdentity(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    setWorkspaceId(workspaceId);
    setUserId(userId);
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setIdentityMessage("Identity saved.");
  }

  function onClearIdentity(): void {
    setWorkspaceId("");
    setUserId("");
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setIdentityMessage("Stored IDs cleared. Env values (if set) are now in effect.");
  }

  async function onSaveWorkspaceSettings(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSavingSettings(true);
    setError(null);
    setSettingsMessage(null);
    try {
      const updated = await patchWorkspaceSettings({
        openai_api_key: openaiApiKey.trim() || null,
        anthropic_api_key: anthropicApiKey.trim() || null,
        preferred_ai_provider: preferredAiProvider,
        google_places_api_key: googleApiKey.trim() || null,
        google_oauth_client_id: googleOAuthClientId.trim() || null,
        google_oauth_client_secret: googleOAuthClientSecret.trim() || null,
        gmail_oauth_redirect_uri: gmailOAuthRedirectUri.trim() || null
      });
      setOpenaiApiKey(updated.openai_api_key ?? "");
      setAnthropicApiKey(updated.anthropic_api_key ?? "");
      setPreferredAiProvider(updated.preferred_ai_provider ?? "auto");
      setGoogleApiKey(updated.google_places_api_key ?? "");
      setGoogleOAuthClientId(updated.google_oauth_client_id ?? "");
      setGoogleOAuthClientSecret(updated.google_oauth_client_secret ?? "");
      setGmailOAuthRedirectUri(updated.gmail_oauth_redirect_uri ?? "");
      setSettingsMessage("Integration settings saved.");
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSavingSettings(false);
    }
  }

  async function onSaveGeneralProfile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSavingProfile(true);
    setError(null);
    setProfileMessage(null);
    try {
      const updated = await patchWorkspaceProfile({
        business_name: businessName.trim() || null,
        business_description: businessDescription.trim() || null,
        industries_served: csvToList(industriesServed),
        service_specialties: csvToList(serviceSpecialties),
        service_area: serviceArea.trim() || null,
        sender_name: senderName.trim() || null,
        sender_title: senderTitle.trim() || null,
        sender_phone: senderPhone.trim() || null,
        sender_email: senderEmail.trim() || null,
      });
      setBusinessName(updated.business_name ?? "");
      setBusinessDescription(updated.business_description ?? "");
      setIndustriesServed((updated.industries_served ?? []).join(", "));
      setServiceSpecialties((updated.service_specialties ?? []).join(", "));
      setServiceArea(updated.service_area ?? "");
      setSenderName(updated.sender_name ?? "");
      setSenderTitle(updated.sender_title ?? "");
      setSenderPhone(updated.sender_phone ?? "");
      setSenderEmail(updated.sender_email ?? "");
      setProfileMessage(
        "General workspace profile saved. Regenerate AI strategy (AI Configuration tab) to update target categories and pain points."
      );
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSavingProfile(false);
    }
  }

  async function onSaveAiProfile(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSavingProfile(true);
    setError(null);
    setProfileMessage(null);
    try {
      const updated = await patchWorkspaceProfile({
        preferred_tone: preferredTone.trim() || null,
        outreach_style: outreachStyle.trim() || null,
        preferred_cta: preferredCta.trim() || null,
        do_not_mention: csvToList(doNotMention)
      });
      setPreferredTone(updated.preferred_tone ?? "");
      setOutreachStyle(updated.outreach_style ?? "");
      setPreferredCta(updated.preferred_cta ?? "");
      setDoNotMention((updated.do_not_mention ?? []).join(", "));
      setProfileMessage("AI configuration saved.");
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSavingProfile(false);
    }
  }

  async function onGenerateStrategy(): Promise<void> {
    setGeneratingStrategy(true);
    setError(null);
    setStrategyMessage(null);
    try {
      const generated = await generateWorkspaceAiStrategy();
      applyAiStrategyState(generated);
      setStrategyMessage("AI outreach strategy generated.");
    } catch (generateError) {
      setError(getErrorMessage(generateError));
    } finally {
      setGeneratingStrategy(false);
    }
  }

  async function onSaveStrategySelections(event: FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSavingStrategy(true);
    setError(null);
    setStrategyMessage(null);
    try {
      const updated = await patchWorkspaceAiStrategy({
        selected_target_categories: selectedCategories,
        selected_priority_pain_points: selectedPainPoints,
        selected_cta_style: selectedCtaStyle.trim() || null
      });
      applyAiStrategyState(updated);
      setStrategyMessage("AI strategy selections saved.");
    } catch (saveError) {
      setError(getErrorMessage(saveError));
    } finally {
      setSavingStrategy(false);
    }
  }

  async function loadGmailAliases(): Promise<void> {
    try {
      const result = await getGmailSendAsAliases();
      setGmailAliases(result.aliases);
    } catch {
      // Aliases unavailable — not fatal
      setGmailAliases([]);
    }
  }

  async function onConnectGmail(): Promise<void> {
    setConnectingGmail(true);
    setGmailError(null);
    setGmailMessage(null);
    try {
      const { connect_url } = await getGmailConnectUrl();
      if (!connect_url.startsWith("https://")) {
        throw new Error("Invalid OAuth URL returned from server.");
      }
      window.location.href = connect_url;
    } catch (err) {
      setGmailError(getErrorMessage(err));
      setConnectingGmail(false);
    }
  }

  async function onDisconnectGmail(): Promise<void> {
    setDisconnectingGmail(true);
    setGmailError(null);
    setGmailMessage(null);
    try {
      await disconnectGmail();
      setGmailConnected(false);
      setGmailEmail(null);
      setGmailAliases([]);
      setGmailSendAsEmail("");
      setGmailSendAsDisplayName("");
      setGmailMessage("Gmail disconnected.");
    } catch (err) {
      setGmailError(getErrorMessage(err));
    } finally {
      setDisconnectingGmail(false);
    }
  }

  async function onSaveGmailAlias(event: React.FormEvent<HTMLFormElement>): Promise<void> {
    event.preventDefault();
    setSavingGmailAlias(true);
    setGmailError(null);
    setGmailMessage(null);
    try {
      const alias = gmailAliases.find((a) => a.send_as_email === gmailSendAsEmail);
      await patchWorkspaceSettings({
        gmail_send_as_email: gmailSendAsEmail.trim() || null,
        gmail_send_as_display_name: (alias?.display_name ?? gmailSendAsDisplayName.trim()) || null,
      });
      setGmailMessage("Send-as address saved. Future emails will use this address.");
    } catch (err) {
      setGmailError(getErrorMessage(err));
    } finally {
      setSavingGmailAlias(false);
    }
  }

  async function onImportDatabase(event: React.ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0];
    if (!file) return;
    setImportingDb(true);
    setDbImportError(null);
    setDbImportMessage(null);
    try {
      const result = await importDatabase(file);
      setDbImportMessage(result.message);
    } catch (importError) {
      setDbImportError(getErrorMessage(importError));
    } finally {
      setImportingDb(false);
      // reset file input so the same file can be re-selected if needed
      event.target.value = "";
    }
  }

  const strategyGenerated = aiStrategy?.generated_strategy;
  const strategyIdealCustomers = strategyGenerated?.ideal_customers ?? [];
  const strategyPainPoints = strategyGenerated?.priority_pain_points ?? [];
  const strategyRapportPoints = strategyGenerated?.rapport_points ?? [];
  const strategyCtas = strategyGenerated?.cta_recommendations ?? [];
  const strategyGuardrails = strategyGenerated?.guardrails;
  const strategyClassifications = strategyGenerated?.business_model_classification ?? [];
  const specialtyList = csvToList(serviceSpecialties);

  return (
    <div className="stack">
      <section className="hero-panel">
        <header className="page-header" style={{ marginBottom: 0 }}>
          <div>
            <h1 className="page-title">Settings</h1>
            <p className="page-subtitle">Configure workspace profile, integrations, and AI defaults.</p>
          </div>
        </header>
      </section>

      {error ? <div className="error">{error}</div> : null}
      {loading ? <div className="card"><span className="muted">Loading settings...</span></div> : null}

      <section className="card stack">
        <div className="settings-tabs">
          <button
            type="button"
            className={`settings-tab ${activeTab === "general" ? "active" : ""}`}
            onClick={() => setActiveTab("general")}
          >
            General
          </button>
          <button
            type="button"
            className={`settings-tab ${activeTab === "integrations" ? "active" : ""}`}
            onClick={() => setActiveTab("integrations")}
          >
            Integrations
          </button>
          <button
            type="button"
            className={`settings-tab ${activeTab === "ai" ? "active" : ""}`}
            onClick={() => setActiveTab("ai")}
          >
            AI Configuration
          </button>
        </div>

        {activeTab === "general" ? (
          <form className="stack" onSubmit={onSaveGeneralProfile}>
            <h2>Workspace Profile</h2>
            <div className="row">
              <div className="field">
                <label htmlFor="business_name">Business Name</label>
                <input
                  id="business_name"
                  value={businessName}
                  onChange={(event) => setBusinessName(event.target.value)}
                  placeholder="Acme Managed IT"
                />
              </div>
              <div className="field">
                <label htmlFor="service_area">Service Area</label>
                <input
                  id="service_area"
                  value={serviceArea}
                  onChange={(event) => setServiceArea(event.target.value)}
                  placeholder="Northern California"
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="business_description">Business Description</label>
              <textarea
                id="business_description"
                value={businessDescription}
                onChange={(event) => setBusinessDescription(event.target.value)}
                placeholder="Managed IT services for restaurants and hospitality groups."
              />
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="industries_served">Industries Served (comma-separated)</label>
                <input
                  id="industries_served"
                  value={industriesServed}
                  onChange={(event) => setIndustriesServed(event.target.value)}
                  placeholder="restaurants, hospitality, retail"
                />
              </div>
              <div className="field">
                <label htmlFor="service_specialties">Service Specialties (comma-separated)</label>
                <input
                  id="service_specialties"
                  value={serviceSpecialties}
                  onChange={(event) => setServiceSpecialties(event.target.value)}
                  placeholder="wifi reliability, POS networking, camera systems"
                />
              </div>
            </div>
            <h3 style={{ marginTop: 20, marginBottom: 8, fontSize: ".95rem" }}>Sender Contact Info</h3>
            <p className="muted" style={{ marginBottom: 10, fontSize: ".82rem" }}>Used in email signatures. Without these, AI-generated emails may contain placeholder brackets.</p>
            <div className="row">
              <div className="field">
                <label htmlFor="sender_name">Your Name</label>
                <input
                  id="sender_name"
                  value={senderName}
                  onChange={(event) => setSenderName(event.target.value)}
                  placeholder="John Smith"
                />
              </div>
              <div className="field">
                <label htmlFor="sender_title">Your Title / Position</label>
                <input
                  id="sender_title"
                  value={senderTitle}
                  onChange={(event) => setSenderTitle(event.target.value)}
                  placeholder="Owner"
                />
              </div>
            </div>
            <div className="row">
              <div className="field">
                <label htmlFor="sender_phone">Phone Number</label>
                <input
                  id="sender_phone"
                  value={senderPhone}
                  onChange={(event) => setSenderPhone(event.target.value)}
                  placeholder="(555) 123-4567"
                />
              </div>
              <div className="field">
                <label htmlFor="sender_email">Email Address</label>
                <input
                  id="sender_email"
                  value={senderEmail}
                  onChange={(event) => setSenderEmail(event.target.value)}
                  placeholder="john@yourcompany.com"
                />
              </div>
            </div>
            {profileMessage ? <div className="success">{profileMessage}</div> : null}
            <div className="inline-actions">
              <button type="submit" className="btn-secondary" disabled={savingProfile || loading}>
                {savingProfile ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </form>
        ) : null}

        {activeTab === "integrations" ? (
          <div className="stack">
            {/* ── Gmail ── */}
            <section className="subcard stack">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
                <h2 style={{ margin: 0 }}>Gmail</h2>
                {gmailConnected ? (
                  <span style={{ fontSize: ".82rem", color: "var(--green, #3fb950)", fontWeight: 600 }}>● Connected</span>
                ) : (
                  <span style={{ fontSize: ".82rem", color: "var(--text-secondary)", fontWeight: 600 }}>○ Not connected</span>
                )}
              </div>

              {gmailConnected ? (
                <div className="stack">
                  <div className="kv-grid">
                    <div className="kv">
                      <strong>Signed in as</strong>
                      {gmailEmail ?? "—"}
                    </div>
                  </div>

                  {/* Send-as alias picker */}
                  <form className="stack" onSubmit={(e) => void onSaveGmailAlias(e)}>
                    <h3 style={{ marginTop: 4, marginBottom: 4, fontSize: ".92rem" }}>Send emails as</h3>
                    <p className="muted" style={{ fontSize: ".83rem", marginBottom: 6 }}>
                      Choose which address outreach emails appear to come from. Aliases must already be verified in Gmail.
                    </p>

                    {gmailAliases.length > 0 ? (
                      <div className="field">
                        <label htmlFor="gmail_send_as_select">From address</label>
                        <select
                          id="gmail_send_as_select"
                          value={gmailSendAsEmail}
                          onChange={(e) => {
                            setGmailSendAsEmail(e.target.value);
                            const alias = gmailAliases.find((a) => a.send_as_email === e.target.value);
                            setGmailSendAsDisplayName(alias?.display_name ?? "");
                          }}
                        >
                          <option value="">— default (primary inbox) —</option>
                          {gmailAliases.map((alias) => (
                            <option key={alias.send_as_email} value={alias.send_as_email}>
                              {alias.display_name
                                ? `${alias.display_name} <${alias.send_as_email}>`
                                : alias.send_as_email}
                              {alias.is_primary ? " (primary)" : ""}
                              {alias.is_default ? " (default)" : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                    ) : (
                      <div className="row" style={{ alignItems: "center", gap: 8 }}>
                        <div className="field" style={{ flex: 1 }}>
                          <label htmlFor="gmail_send_as_manual">From address</label>
                          <input
                            id="gmail_send_as_manual"
                            type="email"
                            placeholder={gmailEmail ?? "you@example.com"}
                            value={gmailSendAsEmail}
                            onChange={(e) => setGmailSendAsEmail(e.target.value)}
                          />
                        </div>
                        <div className="field" style={{ flex: 1 }}>
                          <label htmlFor="gmail_send_as_name">Display name (optional)</label>
                          <input
                            id="gmail_send_as_name"
                            type="text"
                            placeholder="John Smith"
                            value={gmailSendAsDisplayName}
                            onChange={(e) => setGmailSendAsDisplayName(e.target.value)}
                          />
                        </div>
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{ marginTop: 20, flexShrink: 0 }}
                          onClick={() => void loadGmailAliases()}
                        >
                          Load aliases
                        </button>
                      </div>
                    )}

                    {gmailMessage ? <div className="success">{gmailMessage}</div> : null}
                    {gmailError ? <div className="error">{gmailError}</div> : null}

                    <div className="inline-actions">
                      <button type="submit" className="btn-secondary" disabled={savingGmailAlias}>
                        {savingGmailAlias ? "Saving..." : "Save Send-as Address"}
                      </button>
                      <button
                        type="button"
                        className="btn-secondary"
                        style={{ color: "var(--red, #f85149)" }}
                        disabled={disconnectingGmail}
                        onClick={() => void onDisconnectGmail()}
                      >
                        {disconnectingGmail ? "Disconnecting..." : "Disconnect Gmail"}
                      </button>
                    </div>
                  </form>
                </div>
              ) : (
                <div className="stack">
                  <p className="muted" style={{ fontSize: ".88rem" }}>
                    Connect your Gmail account to send outreach emails and sync replies directly through CRM Command.
                  </p>
                  {gmailError ? <div className="error">{gmailError}</div> : null}
                  {gmailMessage ? <div className="success">{gmailMessage}</div> : null}
                  <div className="inline-actions">
                    <button
                      type="button"
                      className="btn-primary"
                      disabled={connectingGmail || loading}
                      onClick={() => void onConnectGmail()}
                    >
                      {connectingGmail ? "Redirecting…" : "Connect Gmail"}
                    </button>
                  </div>
                  <p className="muted" style={{ fontSize: ".78rem" }}>
                    You&apos;ll need a Google OAuth client configured below before connecting.
                  </p>
                </div>
              )}
            </section>

            {/* ── API Keys ── */}
            <form className="stack" onSubmit={onSaveWorkspaceSettings}>
              <h2>API Keys</h2>
              <p className="muted" style={{ fontSize: "0.88rem", marginTop: -4 }}>
                Anthropic (Claude) is used for email generation when configured — it follows outreach instructions more reliably than GPT.
              </p>
              <div className="row">
                <div className="field">
                  <label htmlFor="anthropic_api_key">
                    Anthropic API Key <span style={{ fontSize: ".75rem", fontWeight: 600, color: "var(--blue)" }}>Recommended for emails</span>
                  </label>
                  <input
                    id="anthropic_api_key"
                    type="password"
                    placeholder="sk-ant-..."
                    value={anthropicApiKey}
                    onChange={(event) => setAnthropicApiKey(event.target.value)}
                  />
                </div>
                <div className="field">
                  <label htmlFor="openai_api_key">OpenAI API Key</label>
                  <input
                    id="openai_api_key"
                    type="password"
                    placeholder="sk-..."
                    value={openaiApiKey}
                    onChange={(event) => setOpenaiApiKey(event.target.value)}
                  />
                </div>
              </div>
              <div className="field" style={{ maxWidth: 380 }}>
                <label htmlFor="preferred_ai_provider">Email AI Provider</label>
                <select
                  id="preferred_ai_provider"
                  value={preferredAiProvider}
                  onChange={(event) => setPreferredAiProvider(event.target.value)}
                >
                  <option value="auto">Auto (Claude preferred, GPT fallback)</option>
                  <option value="anthropic">Force Claude (Anthropic)</option>
                  <option value="openai">Force GPT (OpenAI)</option>
                </select>
              </div>

              <div className="row">
                <div className="field">
                  <label htmlFor="google_places_api_key">Google Places API Key</label>
                  <input
                    id="google_places_api_key"
                    type="password"
                    placeholder="AIza..."
                    value={googleApiKey}
                    onChange={(event) => setGoogleApiKey(event.target.value)}
                  />
                </div>
                <div className="field" />
              </div>

              <h3 style={{ marginTop: "1rem", marginBottom: 0 }}>Google OAuth (for Gmail)</h3>
              <p className="muted" style={{ marginTop: 4, fontSize: "0.88rem" }}>
                Web application credentials from Google Cloud Console. The authorized redirect URI must match the value
                below (or your server&apos;s <code>GMAIL_OAUTH_REDIRECT_URI</code> env var).
              </p>
              <div className="field">
                <label htmlFor="google_oauth_client_id">OAuth Client ID</label>
                <input
                  id="google_oauth_client_id"
                  type="text"
                  autoComplete="off"
                  placeholder="xxx.apps.googleusercontent.com"
                  value={googleOAuthClientId}
                  onChange={(event) => setGoogleOAuthClientId(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="google_oauth_client_secret">OAuth Client Secret</label>
                <input
                  id="google_oauth_client_secret"
                  type="password"
                  autoComplete="new-password"
                  placeholder="GOCSPX-..."
                  value={googleOAuthClientSecret}
                  onChange={(event) => setGoogleOAuthClientSecret(event.target.value)}
                />
              </div>
              <div className="field">
                <label htmlFor="gmail_oauth_redirect_uri">OAuth Redirect URI (optional override)</label>
                <input
                  id="gmail_oauth_redirect_uri"
                  type="url"
                  autoComplete="off"
                  placeholder="http://localhost:8000/api/v1/integrations/gmail/callback"
                  value={gmailOAuthRedirectUri}
                  onChange={(event) => setGmailOAuthRedirectUri(event.target.value)}
                />
              </div>

              {settingsMessage ? <div className="success">{settingsMessage}</div> : null}
              <div className="inline-actions">
                <button type="submit" className="btn-secondary" disabled={savingSettings || loading}>
                  {savingSettings ? "Saving..." : "Save API Keys"}
                </button>
              </div>
            </form>
          </div>
        ) : null}

        {activeTab === "ai" ? (
          <div className="stack">
            <form className="stack" onSubmit={onSaveAiProfile}>
              <h2>AI Configuration</h2>
              <div className="row">
                <div className="field">
                  <label htmlFor="preferred_tone">Preferred Tone</label>
                  <input
                    id="preferred_tone"
                    value={preferredTone}
                    onChange={(event) => setPreferredTone(event.target.value)}
                    placeholder="professional, warm"
                  />
                </div>
                <div className="field">
                  <label htmlFor="outreach_style">Outreach Style</label>
                  <input
                    id="outreach_style"
                    value={outreachStyle}
                    onChange={(event) => setOutreachStyle(event.target.value)}
                    placeholder="consultative"
                  />
                </div>
              </div>
              <div className="field">
                <label htmlFor="preferred_cta">Default CTA</label>
                <textarea
                  id="preferred_cta"
                  value={preferredCta}
                  onChange={(event) => setPreferredCta(event.target.value)}
                  placeholder="Would you be open to a 15-minute call this week?"
                />
              </div>
              <div className="field">
                <label htmlFor="do_not_mention">Things To Avoid (comma-separated)</label>
                <input
                  id="do_not_mention"
                  value={doNotMention}
                  onChange={(event) => setDoNotMention(event.target.value)}
                  placeholder="pricing guarantees, competitor names"
                />
              </div>
              {profileMessage ? <div className="success">{profileMessage}</div> : null}
              <div className="inline-actions">
                <button type="submit" className="btn-secondary" disabled={savingProfile || loading}>
                  {savingProfile ? "Saving..." : "Save Settings"}
                </button>
              </div>
            </form>

            <section className="subcard stack">
              <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
                <h3>AI Outreach Strategy</h3>
                <button type="button" className="btn-primary" onClick={() => void onGenerateStrategy()} disabled={generatingStrategy || loading}>
                  {generatingStrategy ? "Generating..." : "Generate AI Outreach Strategy"}
                </button>
              </div>
              <p className="muted">
                Generate targeting suggestions, then choose which categories and pain points Agent 2 should use. Rapport points are common hooks Agent 2 will look for when building emails.
              </p>

              {!strategyGenerated ? (
                <div className="empty-state">No strategy generated yet. Generate once to review and select targeting guidance.</div>
              ) : (
                <form className="stack" onSubmit={onSaveStrategySelections}>
                  <div className="kv-grid">
                    <div className="kv">
                      <strong>Core Positioning</strong>
                      {strategyGenerated.core_positioning || "-"}
                    </div>
                    <div className="kv">
                      <strong>Version</strong>
                      {aiStrategy.version}
                    </div>
                    <div className="kv">
                      <strong>Last Generated</strong>
                      {aiStrategy.last_generated_at ? new Date(aiStrategy.last_generated_at).toLocaleString() : "-"}
                    </div>
                    <div className="kv">
                      <strong>Business Model Classification</strong>
                      {strategyClassifications.length > 0 ? strategyClassifications.join(", ") : "-"}
                    </div>
                  </div>

                  <div className="row">
                    <div className="field">
                      <label>Suggested Categories</label>
                      <div className="stack">
                        {strategyIdealCustomers.map((item) => (
                          <label key={item.category} className="check-row">
                            <input
                              type="checkbox"
                              checked={selectedCategories.includes(item.category)}
                              onChange={() => setSelectedCategories((prev) => toggleListItem(prev, item.category))}
                            />
                            <span className="check-row-body">
                              <strong>{item.display_name}</strong>
                              <span className="muted">(priority {item.priority})</span>
                              <span className="muted">Category key: {item.category}</span>
                              <span className="muted">{item.why_fit}</span>
                            </span>
                          </label>
                        ))}
                      </div>
                    </div>
                    <div className="field">
                      <label>Suggested Pain Points</label>
                      <div className="stack">
                        {strategyPainPoints.map((item) => {
                          const specialtyMatches = inferPainMatchesSpecialties(item.label, item.why_relevant, specialtyList);
                          return (
                            <label key={item.key} className="check-row">
                              <input
                                type="checkbox"
                                checked={selectedPainPoints.includes(item.key)}
                                onChange={() => setSelectedPainPoints((prev) => toggleListItem(prev, item.key))}
                              />
                              <span className="check-row-body">
                                <strong>{item.label}</strong>
                                <span className="muted">{item.why_relevant}</span>
                                <span className="muted">
                                  Matches specialties: {specialtyMatches.length ? specialtyMatches.join(", ") : "No direct keyword match"}
                                </span>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="field">
                    <label>Common Rapport Points (by business type)</label>
                    <p className="muted" style={{ marginTop: 4, marginBottom: 8 }}>
                      Agent 2 will look for these signals in the lead&apos;s website to open emails with genuine relevance.
                    </p>
                    <div className="stack">
                      {strategyRapportPoints.map((item) => (
                        <div key={item.category} className="kv">
                          <strong>{item.display_name}</strong>
                          <div className="muted" style={{ marginTop: 6 }}>
                            {item.hooks.join(" • ")}
                          </div>
                        </div>
                      ))}
                      {strategyRapportPoints.length === 0 ? (
                        <span className="muted">No rapport points generated. Regenerate strategy after updating profile.</span>
                      ) : null}
                    </div>
                  </div>

                  <div className="field">
                    <label htmlFor="selected_cta_style">Preferred CTA Style</label>
                    <select
                      id="selected_cta_style"
                      value={selectedCtaStyle}
                      onChange={(event) => setSelectedCtaStyle(event.target.value)}
                    >
                      <option value="">No preference</option>
                      {strategyCtas.map((cta) => (
                        <option key={cta.key} value={cta.key}>
                          {cta.label}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="row">
                    <div className="field">
                      <label>Guardrails: Avoid Claims</label>
                      <div className="muted">{strategyGuardrails?.avoid_claims.join(", ") || "-"}</div>
                    </div>
                    <div className="field">
                      <label>Guardrails: Avoid Tone</label>
                      <div className="muted">{strategyGuardrails?.avoid_tone.join(", ") || "-"}</div>
                    </div>
                  </div>
                  <div className="field">
                    <label>Guardrails: Notes</label>
                    <div className="muted">{strategyGuardrails?.notes.join(", ") || "-"}</div>
                  </div>

                  {strategyMessage ? <div className="success">{strategyMessage}</div> : null}
                  <div className="inline-actions">
                    <button type="submit" className="btn-secondary" disabled={savingStrategy || loading}>
                      {savingStrategy ? "Saving..." : "Save Selections"}
                    </button>
                  </div>
                </form>
              )}
            </section>
          </div>
        ) : null}
      </section>

      <section className="card stack">
        <h2>Database</h2>
        <p className="muted" style={{ fontSize: ".88rem" }}>
          Export your data as a portable <code>.db</code> file to back up or transfer to another machine.
          Importing will replace the current database — the previous file is backed up automatically.
        </p>

        <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-start" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: ".82rem", fontWeight: 500 }}>Export</span>
            <a
              href={getDbExportUrl()}
              download="crm_export.db"
              className="btn-secondary"
              style={{ display: "inline-block", textDecoration: "none" }}
            >
              Download Database
            </a>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            <span style={{ fontSize: ".82rem", fontWeight: 500 }}>Import</span>
            <label className="btn-secondary" style={{ cursor: "pointer", display: "inline-block" }}>
              {importingDb ? "Uploading…" : "Import Database (.db)"}
              <input
                type="file"
                accept=".db"
                style={{ display: "none" }}
                disabled={importingDb}
                onChange={(e) => void onImportDatabase(e)}
              />
            </label>
            <span className="muted" style={{ fontSize: ".78rem" }}>
              Replaces the active database. Restart the app after import.
            </span>
          </div>
        </div>

        {dbImportMessage ? <div className="success">{dbImportMessage}</div> : null}
        {dbImportError ? <div className="error">{dbImportError}</div> : null}
      </section>

      <section className="card stack">
        <h2>Dev Identity</h2>
        <div className="kv-grid">
          <div className="kv">
            <strong>API Base</strong>
            {getApiBaseForDisplay()}
          </div>
          <div className="kv">
            <strong>Current Workspace ID</strong>
            {workspaceId || "(missing)"}
          </div>
          <div className="kv">
            <strong>Current User ID</strong>
            {userId || "(missing)"}
          </div>
        </div>

        <form className="stack" onSubmit={onSaveIdentity}>
          <div className="row">
            <div className="field">
              <label htmlFor="workspace_id">Workspace ID</label>
              <input
                id="workspace_id"
                placeholder="workspace uuid"
                value={workspaceId}
                onChange={(event) => setWorkspaceInput(event.target.value)}
              />
            </div>
            <div className="field">
              <label htmlFor="user_id">User ID</label>
              <input id="user_id" placeholder="user uuid" value={userId} onChange={(event) => setUserInput(event.target.value)} />
            </div>
          </div>

          {identityMessage ? <div className="success">{identityMessage}</div> : null}

          <div className="inline-actions">
            <button type="submit" className="btn-primary">
              Save Identity
            </button>
            <button type="button" className="btn-secondary" onClick={onClearIdentity}>
              Clear
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
