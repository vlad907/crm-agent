"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  API_BASE,
  ApiError,
  getWorkspaceProfile,
  getWorkspaceSettings,
  patchWorkspaceProfile,
  patchWorkspaceSettings
} from "@/src/lib/api";
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

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>("general");
  const [workspaceId, setWorkspaceInput] = useState("");
  const [userId, setUserInput] = useState("");

  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [googleApiKey, setGoogleApiKey] = useState("");
  const [gmailConnected, setGmailConnected] = useState(false);

  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [industriesServed, setIndustriesServed] = useState("");
  const [serviceSpecialties, setServiceSpecialties] = useState("");
  const [serviceArea, setServiceArea] = useState("");
  const [preferredTone, setPreferredTone] = useState("");
  const [outreachStyle, setOutreachStyle] = useState("");
  const [preferredCta, setPreferredCta] = useState("");
  const [doNotMention, setDoNotMention] = useState("");

  const [identityMessage, setIdentityMessage] = useState<string | null>(null);
  const [settingsMessage, setSettingsMessage] = useState<string | null>(null);
  const [profileMessage, setProfileMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingSettings, setSavingSettings] = useState(false);
  const [savingProfile, setSavingProfile] = useState(false);

  useEffect(() => {
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setLoading(true);
    setError(null);
    void Promise.all([getWorkspaceSettings(), getWorkspaceProfile()])
      .then(([settings, profile]) => {
        setOpenaiApiKey(settings.openai_api_key ?? "");
        setGoogleApiKey(settings.google_places_api_key ?? "");
        setGmailConnected(Boolean(settings.gmail_connected));

        setBusinessName(profile.business_name ?? "");
        setBusinessDescription(profile.business_description ?? "");
        setIndustriesServed((profile.industries_served ?? []).join(", "));
        setServiceSpecialties((profile.service_specialties ?? []).join(", "));
        setServiceArea(profile.service_area ?? "");
        setPreferredTone(profile.preferred_tone ?? "");
        setOutreachStyle(profile.outreach_style ?? "");
        setPreferredCta(profile.preferred_cta ?? "");
        setDoNotMention((profile.do_not_mention ?? []).join(", "));
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
        google_places_api_key: googleApiKey.trim() || null,
        gmail_connected: gmailConnected
      });
      setOpenaiApiKey(updated.openai_api_key ?? "");
      setGoogleApiKey(updated.google_places_api_key ?? "");
      setGmailConnected(Boolean(updated.gmail_connected));
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
        service_area: serviceArea.trim() || null
      });
      setBusinessName(updated.business_name ?? "");
      setBusinessDescription(updated.business_description ?? "");
      setIndustriesServed((updated.industries_served ?? []).join(", "));
      setServiceSpecialties((updated.service_specialties ?? []).join(", "));
      setServiceArea(updated.service_area ?? "");
      setProfileMessage("General workspace profile saved.");
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
            {profileMessage ? <div className="success">{profileMessage}</div> : null}
            <div className="inline-actions">
              <button type="submit" className="btn-secondary" disabled={savingProfile || loading}>
                {savingProfile ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </form>
        ) : null}

        {activeTab === "integrations" ? (
          <form className="stack" onSubmit={onSaveWorkspaceSettings}>
            <h2>Integrations</h2>
            <div className="row">
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
            </div>
            <label style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
              <input
                type="checkbox"
                checked={gmailConnected}
                onChange={(event) => setGmailConnected(event.target.checked)}
              />
              Gmail connected
            </label>
            {settingsMessage ? <div className="success">{settingsMessage}</div> : null}
            <div className="inline-actions">
              <button type="submit" className="btn-secondary" disabled={savingSettings || loading}>
                {savingSettings ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </form>
        ) : null}

        {activeTab === "ai" ? (
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
        ) : null}
      </section>

      <section className="card stack">
        <h2>Dev Identity</h2>
        <div className="kv-grid">
          <div className="kv">
            <strong>API Base</strong>
            {API_BASE}
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
