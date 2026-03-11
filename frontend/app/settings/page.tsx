"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  API_BASE,
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
  const [googleApiKey, setGoogleApiKey] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [businessDescription, setBusinessDescription] = useState("");
  const [industriesServed, setIndustriesServed] = useState("");
  const [serviceSpecialties, setServiceSpecialties] = useState("");
  const [serviceArea, setServiceArea] = useState("");
  const [preferredTone, setPreferredTone] = useState("");
  const [outreachStyle, setOutreachStyle] = useState("");
  const [preferredCta, setPreferredCta] = useState("");
  const [doNotMention, setDoNotMention] = useState("");
  const [aiStrategy, setAiStrategy] = useState<WorkspaceAiStrategy | null>(null);
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [selectedPainPoints, setSelectedPainPoints] = useState<string[]>([]);
  const [selectedServiceAngles, setSelectedServiceAngles] = useState<string[]>([]);
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

  function applyAiStrategyState(strategy: WorkspaceAiStrategy): void {
    setAiStrategy(strategy);
    setSelectedCategories(strategy.selected_target_categories ?? []);
    setSelectedPainPoints(strategy.selected_priority_pain_points ?? []);
    setSelectedServiceAngles(strategy.selected_service_angles ?? []);
    setSelectedCtaStyle(strategy.selected_cta_style ?? "");
  }

  useEffect(() => {
    setWorkspaceInput(getWorkspaceId());
    setUserInput(getUserId());
    setLoading(true);
    setError(null);
    void Promise.all([getWorkspaceSettings(), getWorkspaceProfile(), getWorkspaceAiStrategy()])
      .then(([settings, profile, strategy]) => {
        setOpenaiApiKey(settings.openai_api_key ?? "");
        setGoogleApiKey(settings.google_places_api_key ?? "");

        setBusinessName(profile.business_name ?? "");
        setBusinessDescription(profile.business_description ?? "");
        setIndustriesServed((profile.industries_served ?? []).join(", "));
        setServiceSpecialties((profile.service_specialties ?? []).join(", "));
        setServiceArea(profile.service_area ?? "");
        setPreferredTone(profile.preferred_tone ?? "");
        setOutreachStyle(profile.outreach_style ?? "");
        setPreferredCta(profile.preferred_cta ?? "");
        setDoNotMention((profile.do_not_mention ?? []).join(", "));

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
        google_places_api_key: googleApiKey.trim() || null
      });
      setOpenaiApiKey(updated.openai_api_key ?? "");
      setGoogleApiKey(updated.google_places_api_key ?? "");
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
        selected_service_angles: selectedServiceAngles,
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

  const strategyGenerated = aiStrategy?.generated_strategy;
  const strategyIdealCustomers = strategyGenerated?.ideal_customers ?? [];
  const strategyPainPoints = strategyGenerated?.priority_pain_points ?? [];
  const strategyAngles = strategyGenerated?.service_angles ?? [];
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
            {settingsMessage ? <div className="success">{settingsMessage}</div> : null}
            <div className="inline-actions">
              <button type="submit" className="btn-secondary" disabled={savingSettings || loading}>
                {savingSettings ? "Saving..." : "Save Settings"}
              </button>
            </div>
          </form>
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
                Generate targeting suggestions, then choose which categories, pain points, and service angles Agent 2 should use.
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
                          <label key={item.category} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                            <input
                              type="checkbox"
                              checked={selectedCategories.includes(item.category)}
                              onChange={() => setSelectedCategories((prev) => toggleListItem(prev, item.category))}
                            />
                            <span>
                              <strong>{item.display_name}</strong> <span className="muted">(priority {item.priority})</span>
                              <div className="muted">Category key: {item.category}</div>
                              <div className="muted">{item.why_fit}</div>
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
                            <label key={item.key} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                              <input
                                type="checkbox"
                                checked={selectedPainPoints.includes(item.key)}
                                onChange={() => setSelectedPainPoints((prev) => toggleListItem(prev, item.key))}
                              />
                              <span>
                                <strong>{item.label}</strong>
                                <div className="muted">{item.why_relevant}</div>
                                <div className="muted">
                                  Matches specialties: {specialtyMatches.length ? specialtyMatches.join(", ") : "No direct keyword match"}
                                </div>
                              </span>
                            </label>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  <div className="field">
                    <label>Suggested Service Angles</label>
                    <div className="stack">
                      {strategyAngles.map((item) => (
                        <label key={item.key} style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                          <input
                            type="checkbox"
                            checked={selectedServiceAngles.includes(item.key)}
                            onChange={() => setSelectedServiceAngles((prev) => toggleListItem(prev, item.key))}
                          />
                          <span>
                            <strong>{item.label}</strong>
                            <div className="muted">Best for: {item.best_for_categories.join(", ") || "-"}</div>
                            <div className="muted">{item.why_relevant || "-"}</div>
                          </span>
                        </label>
                      ))}
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
