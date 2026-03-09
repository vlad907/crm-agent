import { Lead, LeadPipelineSummary } from "@/src/lib/types";

export type LeadStage = "new" | "ingested" | "agent1" | "agent2" | "agent3" | "ready" | "hold" | "sent";

const EMPTY_SUMMARY: LeadPipelineSummary = {
  has_snapshot: false,
  has_agent1_output: false,
  has_draft: false,
  has_agent3_verdict: false,
  final_decision: null,
  computed_stage: "new",
};

function normalizeStage(value: string | undefined): LeadStage {
  const normalized = (value ?? "").toLowerCase();
  if (normalized === "sent") {
    return "sent";
  }
  if (normalized === "ready" || normalized === "ready_to_send" || normalized === "send") {
    return "ready";
  }
  if (normalized === "hold") {
    return "hold";
  }
  if (normalized === "agent3" || normalized === "verified") {
    return "agent3";
  }
  if (normalized === "agent2" || normalized === "draft" || normalized === "drafted") {
    return "agent2";
  }
  if (normalized === "agent1") {
    return "agent1";
  }
  if (normalized === "ingested" || normalized === "enriched") {
    return "ingested";
  }
  return "new";
}

export function resolveLeadPipeline(lead: Lead): LeadPipelineSummary {
  if (lead.pipeline_summary) {
    return {
      ...EMPTY_SUMMARY,
      ...lead.pipeline_summary,
      computed_stage: normalizeStage(lead.pipeline_summary.computed_stage),
    };
  }

  const stage = normalizeStage(lead.status);
  const summary: LeadPipelineSummary = {
    ...EMPTY_SUMMARY,
    computed_stage: stage,
  };

  if (stage === "ingested" || stage === "agent1" || stage === "agent2" || stage === "agent3" || stage === "ready" || stage === "hold" || stage === "sent") {
    summary.has_snapshot = true;
  }
  if (stage === "agent1" || stage === "agent2" || stage === "agent3" || stage === "ready" || stage === "hold" || stage === "sent") {
    summary.has_agent1_output = true;
  }
  if (stage === "agent2" || stage === "agent3" || stage === "ready" || stage === "hold" || stage === "sent") {
    summary.has_draft = true;
  }
  if (stage === "agent3" || stage === "ready" || stage === "hold" || stage === "sent") {
    summary.has_agent3_verdict = true;
  }
  if (stage === "ready") {
    summary.final_decision = "send";
  } else if (stage === "hold") {
    summary.final_decision = "hold";
  }

  return summary;
}

export function stageLabel(stage: LeadStage): string {
  if (stage === "agent1") {
    return "Agent1";
  }
  if (stage === "agent2") {
    return "Drafted";
  }
  if (stage === "agent3") {
    return "Verified";
  }
  if (stage === "ingested") {
    return "Ingested";
  }
  if (stage === "ready") {
    return "Ready";
  }
  if (stage === "hold") {
    return "Hold";
  }
  if (stage === "sent") {
    return "Sent";
  }
  return "New";
}
