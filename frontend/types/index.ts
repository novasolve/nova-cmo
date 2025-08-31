export type Role = "user" | "assistant" | "tool" | "system";

export interface ChatMessage {
  id: string;
  threadId: string;
  role: Role;
  createdAt: string; // ISO
  text?: string; // markdown
  card?: UICard; // rich card payloads below
  event?: LanggraphEvent; // streamed node events
}

export type UICard =
  | CampaignBriefCard
  | SimulationCard
  | OutboxCard
  | RunSummaryCard
  | ErrorGroupCard
  | PolicyDiffCard;

export interface CampaignBriefCard {
  type: "campaign_brief";
  goal: string;
  icp: Record<string, any>;
  limits: { maxSteps: number; maxRepos: number; maxPeople: number };
  risks: string[];
  yaml: string; // canonical config
  actions: ActionButton[]; // e.g., Run L1, Edit YAML
}

export interface SimulationCard {
  type: "simulation";
  forecast: {
    replyRate: { mean: number; low: number; high: number };
    deliverability: { mean: number; low: number; high: number };
    dailyCostUSD: number;
  };
  assumptions: string[];
  warnings: string[];
  actions: ActionButton[];
}

export interface OutboxCard {
  type: "outbox";
  runId: string;
  samples: Array<{
    leadId: string;
    score: number;
    email: string;
    subject: string;
    body: string;
    evidence: Array<{ label: string; url: string }>;
    policy: Array<{
      rule: string;
      status: "ok" | "warn" | "block";
      note?: string;
    }>;
  }>;
  bulkActions: ActionButton[];
}

export interface RunSummaryCard {
  type: "run_summary";
  runId: string;
  status: "running" | "completed" | "failed" | "paused";
  metrics: {
    totalLeads: number;
    emailsSent: number;
    replies: number;
    costUSD: number;
  };
  actions: ActionButton[];
}

export interface ErrorGroupCard {
  type: "error_group";
  errors: Array<{
    id: string;
    message: string;
    count: number;
    lastSeen: string;
    node: string;
  }>;
  actions: ActionButton[];
}

export interface PolicyDiffCard {
  type: "policy_diff";
  changes: Array<{
    field: string;
    oldValue: string;
    newValue: string;
    impact: string;
  }>;
  actions: ActionButton[];
}

export interface ActionButton {
  id: string; // e.g., "run-l1", "approve-all>=80"
  label: string;
  style?: "primary" | "secondary" | "danger";
  payload?: Record<string, any>;
}

export interface LanggraphEvent {
  ts: string;
  node: string; // e.g., "enrich_github_user"
  status: "start" | "ok" | "retry" | "error";
  latencyMs?: number;
  costUSD?: number;
  msg?: string;
}

export interface SSEEvent {
  kind: "message" | "event";
  message?: ChatMessage;
  event?: LanggraphEvent;
}

export interface ChatOptions {
  autopilot?: number;
  budget?: number;
}
