"use client";
import { 
  CampaignBriefCard, 
  SimulationCard, 
  OutboxCard, 
  RunSummaryCard,
  ErrorGroupCard,
  PolicyDiffCard,
  SmokeTestResultsCard 
} from "@/types";

// Demo data for showcasing the console
export const demoBriefCard: CampaignBriefCard = {
  type: "campaign_brief",
  goal: "Find 2000 active Python maintainers from the last 90 days for outreach sequence 123",
  icp: {
    languages: ["Python"],
    activity: "90 days",
    role: "maintainer",
    minStars: 100
  },
  limits: {
    maxSteps: 50,
    maxRepos: 5000,
    maxPeople: 2000
  },
  risks: [
    "GitHub rate limits may slow discovery phase",
    "Email deliverability depends on domain reputation",
    "Some maintainer emails may be outdated"
  ],
  yaml: `campaign:
  name: "Python Maintainers Q1"
  sequence: 123
  budget: 50
  autopilot: 1
  
icp:
  languages: [python]
  activity_days: 90
  min_stars: 100
  
limits:
  max_people: 2000
  max_repos: 5000`,
  actions: [
    { id: "simulate", label: "Simulate", style: "primary" },
    { id: "edit-yaml", label: "Edit YAML", style: "secondary" },
    { id: "run-assisted", label: "Start in Assisted Mode", style: "primary" }
  ]
};

export const demoSimCard: SimulationCard = {
  type: "simulation",
  forecast: {
    replyRate: { mean: 0.12, low: 0.08, high: 0.18 },
    deliverability: { mean: 0.94, low: 0.89, high: 0.97 },
    dailyCostUSD: 47.50
  },
  assumptions: [
    "Based on similar Python developer campaigns",
    "Assumes 15% email bounce rate",
    "Reply rate varies by maintainer activity level"
  ],
  warnings: [
    "High-profile maintainers may have strict spam filters",
    "Consider A/B testing subject lines for better open rates"
  ],
  actions: [
    { id: "run-assisted", label: "Start in Assisted Mode", style: "primary" },
    { id: "open-outbox", label: "Preview Outbox", style: "secondary" },
    { id: "explain-forecast", label: "Explain Forecast", style: "secondary" }
  ]
};

export const demoOutboxCard: OutboxCard = {
  type: "outbox",
  runId: "run-20240101-123456",
  samples: [
    {
      leadId: "lead-001",
      score: 87,
      email: "gvanrossum@python.org",
      subject: "Your Python AST work caught our attention",
      body: "Hi Guido,\n\nI noticed your recent contributions to Python's AST implementation...",
      evidence: [
        { label: "Recent commits", url: "https://github.com/python/cpython/commits?author=gvanrossum" },
        { label: "AST improvements", url: "https://github.com/python/cpython/pull/12345" }
      ],
      policy: [
        { rule: "personalization_required", status: "ok" },
        { rule: "evidence_count >= 2", status: "ok" },
        { rule: "no_generic_templates", status: "ok" }
      ]
    },
    {
      leadId: "lead-002",
      score: 92,
      email: "barry@python.org",
      subject: "Email package modernization insights",
      body: "Hi Barry,\n\nYour work on the email package has been impressive...",
      evidence: [
        { label: "Email package", url: "https://github.com/python/cpython/tree/main/Lib/email" },
        { label: "PEP 594", url: "https://www.python.org/dev/peps/pep-0594/" }
      ],
      policy: [
        { rule: "personalization_required", status: "ok" },
        { rule: "evidence_count >= 2", status: "ok" },
        { rule: "no_generic_templates", status: "ok" }
      ]
    }
  ],
  bulkActions: [
    { id: "approve-all-80", label: "Approve ≥ 80", style: "primary" },
    { id: "create-rule", label: "Create Rule", style: "secondary" }
  ]
};

export const demoRunSummaryCard: RunSummaryCard = {
  type: "run_summary",
  runId: "run-20240101-123456",
  status: "completed",
  metrics: {
    totalLeads: 2100,
    emailsSent: 1847,
    replies: 221,
    costUSD: 156.78
  },
  actions: [
    { id: "download-csv", label: "Download CSV", style: "primary" },
    { id: "view-replies", label: "View Replies", style: "secondary" },
    { id: "create-followup", label: "Create Follow-up", style: "secondary" }
  ]
};

export const demoErrorCard: ErrorGroupCard = {
  type: "error_group",
  errors: [
    {
      id: "err-001",
      message: "GitHub API rate limit exceeded",
      count: 23,
      lastSeen: "2024-01-01T14:32:15Z",
      node: "fetch_github_profile"
    },
    {
      id: "err-002", 
      message: "Email validation timeout",
      count: 7,
      lastSeen: "2024-01-01T14:28:42Z",
      node: "validate_email"
    }
  ],
  actions: [
    { id: "retry-failed", label: "Retry Failed", style: "primary" },
    { id: "adjust-limits", label: "Adjust Limits", style: "secondary" },
    { id: "ignore-errors", label: "Ignore", style: "danger" }
  ]
};

export const demoPolicyCard: PolicyDiffCard = {
  type: "policy_diff",
  changes: [
    {
      field: "personalization.min_evidence_count",
      oldValue: "1",
      newValue: "2",
      impact: "Will require more evidence per email, improving quality but reducing volume"
    },
    {
      field: "tone.formality_level",
      oldValue: "casual",
      newValue: "professional",
      impact: "More formal language may increase credibility with senior maintainers"
    }
  ],
  actions: [
    { id: "apply-changes", label: "Apply Changes", style: "primary" },
    { id: "preview-impact", label: "Preview Impact", style: "secondary" },
    { id: "revert-changes", label: "Revert", style: "danger" }
  ]
};

export const demoSmokeTestCard: SmokeTestResultsCard = {
  type: "smoke_test_results",
  status: "passed",
  duration: 41000, // 41 seconds
  checks: [
    { id: "queue_stream", name: "Queue & Stream", required: true, passed: true, details: "Job created, SSE connected, events flowing" },
    { id: "brief_rendered", name: "Brief Rendered", required: true, passed: true, details: "Campaign Brief card with goal/limits/risks" },
    { id: "simulation_rendered", name: "Simulation Rendered", required: true, passed: true, details: "Simulation Pack with forecasts" },
    { id: "drafts_rendered", name: "Drafts Rendered", required: true, passed: true, details: "3 drafts, all with score ≥80" },
    { id: "budget_guardrail", name: "Budget Guardrail", required: true, passed: true, details: "Used $0.23 of $1.00 cap" },
    { id: "alerts_captured", name: "Alerts Captured", required: true, passed: true, details: "1 error group captured (rate limit)" },
    { id: "policy_preview", name: "Policy Preview", required: true, passed: true, details: "Policy change proposal rendered" },
    { id: "summary_rendered", name: "Summary Rendered", required: true, passed: true, details: "Run Summary with valid metrics" },
    { id: "latency_check", name: "Latency Check", required: false, passed: true, details: "Completed in 41.0s" },
    { id: "determinism_check", name: "Determinism Check", required: false, passed: true, details: "Fixture hash matches expected" }
  ],
  metrics: {
    eventsStreamed: 47,
    cardsRendered: 7,
    draftsCount: 3,
    budgetUsed: 0.23
  },
  actions: [
    { id: "view-logs", label: "View Logs", style: "secondary" },
    { id: "retry-smoke", label: "Retry", style: "primary" },
    { id: "download-csv", label: "Download CSV", style: "secondary" }
  ]
};
