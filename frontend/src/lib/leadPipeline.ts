import { Lead, LeadPipelineSummary, LeadStatus } from "@/src/lib/types";

export type LeadStage = LeadStatus;
export interface ResolvedLeadPipeline extends Omit<LeadPipelineSummary, "computed_stage"> {
  computed_stage: LeadStage;
}

const EMPTY_SUMMARY: ResolvedLeadPipeline = {
  has_snapshot: false,
  has_agent1_output: false,
  has_draft: false,
  has_agent3_verdict: false,
  final_decision: null,
  computed_stage: "imported",
};

function normalizeStage(value: string | undefined): LeadStage {
  const normalized = (value ?? "").toLowerCase();
  if (normalized === "discovered") {
    return "discovered";
  }
  if (normalized === "imported" || normalized === "new") {
    return "imported";
  }
  if (normalized === "researching") {
    return "researching";
  }
  if (normalized === "researched" || normalized === "ingested" || normalized === "enriched" || normalized === "agent1") {
    return "researched";
  }
  if (normalized === "drafting") {
    return "drafting";
  }
  if (normalized === "draft_ready" || normalized === "agent2" || normalized === "agent3" || normalized === "verified" || normalized === "draft" || normalized === "drafted") {
    return "draft_ready";
  }
  if (normalized === "needs_review" || normalized === "hold") {
    return "needs_review";
  }
  if (normalized === "approved" || normalized === "ready" || normalized === "ready_to_send" || normalized === "send") {
    return "approved";
  }
  if (normalized === "sent") {
    return "sent";
  }
  if (normalized === "replied") {
    return "replied";
  }
  if (normalized === "converted") {
    return "converted";
  }
  if (normalized === "archived") {
    return "archived";
  }
  return "imported";
}

export function resolveLeadPipeline(lead: Lead): ResolvedLeadPipeline {
  if (lead.pipeline_summary) {
    return {
      ...EMPTY_SUMMARY,
      ...lead.pipeline_summary,
      computed_stage: normalizeStage(lead.pipeline_summary.computed_stage),
    };
  }

  const stage = normalizeStage(lead.status);
  const summary: ResolvedLeadPipeline = {
    ...EMPTY_SUMMARY,
    computed_stage: stage,
  };

  if (
    stage === "researched" ||
    stage === "drafting" ||
    stage === "draft_ready" ||
    stage === "needs_review" ||
    stage === "approved" ||
    stage === "sent" ||
    stage === "replied" ||
    stage === "converted" ||
    stage === "archived"
  ) {
    summary.has_snapshot = true;
  }
  if (
    stage === "drafting" ||
    stage === "draft_ready" ||
    stage === "needs_review" ||
    stage === "approved" ||
    stage === "sent" ||
    stage === "replied" ||
    stage === "converted" ||
    stage === "archived"
  ) {
    summary.has_agent1_output = true;
  }
  if (
    stage === "draft_ready" ||
    stage === "needs_review" ||
    stage === "approved" ||
    stage === "sent" ||
    stage === "replied" ||
    stage === "converted" ||
    stage === "archived"
  ) {
    summary.has_draft = true;
  }
  if (
    stage === "needs_review" ||
    stage === "approved" ||
    stage === "sent" ||
    stage === "replied" ||
    stage === "converted" ||
    stage === "archived"
  ) {
    summary.has_agent3_verdict = true;
  }
  if (stage === "approved") {
    summary.final_decision = "send";
  } else if (stage === "needs_review") {
    summary.final_decision = "hold";
  }

  return summary;
}

export function stageLabel(stage: LeadStage): string {
  if (stage === "discovered") {
    return "Discovered";
  }
  if (stage === "imported") {
    return "Imported";
  }
  if (stage === "researching") {
    return "Researching";
  }
  if (stage === "researched") {
    return "Researched";
  }
  if (stage === "drafting") {
    return "Drafting";
  }
  if (stage === "draft_ready") {
    return "Draft Ready";
  }
  if (stage === "needs_review") {
    return "Needs Review";
  }
  if (stage === "approved") {
    return "Approved";
  }
  if (stage === "sent") {
    return "Sent";
  }
  if (stage === "replied") {
    return "Replied";
  }
  if (stage === "converted") {
    return "Converted";
  }
  if (stage === "archived") {
    return "Archived";
  }
  return "Imported";
}
