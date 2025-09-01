// Smoke test fixtures for deterministic testing
export const SMOKE_TEST_FIXTURES = {
  goal: "Find 3 OSS Python maintainers active in the last 30 days",
  limits: {
    max_steps: 10,
    max_repos: 5,
    max_people: 3
  },
  policy: {
    "personalization.min_evidence_count": 2,
    "tone.formality_level": "professional"
  },
  fixtures: {
    maintainers: [
      {
        name: "Pat Maintainer",
        email: "pat@example.com",
        topics: ["AST", "parsing"],
        github_url: "https://github.com/pat-maintainer",
        recent_activity: "2024-01-15T10:30:00Z"
      },
      {
        name: "Sam Maintainer",
        email: "sam@example.com",
        topics: ["email", "PEP 594"],
        github_url: "https://github.com/sam-maintainer",
        recent_activity: "2024-01-20T14:22:00Z"
      },
      {
        name: "Rae Maintainer",
        email: "rae@example.com",
        topics: ["packaging", "pip"],
        github_url: "https://github.com/rae-maintainer",
        recent_activity: "2024-01-25T09:15:00Z"
      }
    ]
  },
  inject: {
    alerts: [
      {
        type: "rate_limit",
        node: "fetch_github_profile",
        occurrences: 3,
        message: "GitHub API rate limit exceeded - retrying with backoff"
      }
    ]
  },
  budget_cap_usd: 1
};

// Expected hash for deterministic validation
export const EXPECTED_FIXTURE_HASH = "smoke-test-v1-abc123";

// Smoke test pass criteria
export interface SmokeTestCheck {
  id: string;
  name: string;
  required: boolean;
  passed: boolean;
  details?: string;
}

export const SMOKE_TEST_CRITERIA = {
  cards_rendered: ["brief", "simulation", "outbox", "summary", "alerts", "policy_changes"],
  min_drafts_count: 2,
  min_draft_score: 80,
  max_budget_used: 1,
  min_alerts_count: 1,
  max_duration_ms: 60000
};

export function createSmokeTestChecks(): SmokeTestCheck[] {
  return [
    {
      id: "queue_stream",
      name: "Queue & Stream",
      required: true,
      passed: false,
      details: "Job created, SSE connected, events flowing"
    },
    {
      id: "brief_rendered",
      name: "Brief Rendered",
      required: true,
      passed: false,
      details: "Campaign Brief card with goal/limits/risks"
    },
    {
      id: "simulation_rendered",
      name: "Simulation Rendered",
      required: true,
      passed: false,
      details: "Simulation Pack with forecasts"
    },
    {
      id: "drafts_rendered",
      name: "Drafts Rendered",
      required: true,
      passed: false,
      details: "≥2 draft emails with scores ≥80"
    },
    {
      id: "budget_guardrail",
      name: "Budget Guardrail",
      required: true,
      passed: false,
      details: "Used ≤ Cap and pauses correctly"
    },
    {
      id: "alerts_captured",
      name: "Alerts Captured",
      required: true,
      passed: false,
      details: "Error injected and Alerts card rendered"
    },
    {
      id: "policy_preview",
      name: "Policy Preview",
      required: true,
      passed: false,
      details: "Policy change proposal rendered"
    },
    {
      id: "summary_rendered",
      name: "Summary Rendered",
      required: true,
      passed: false,
      details: "Run Summary with valid metrics"
    },
    {
      id: "latency_check",
      name: "Latency Check",
      required: false,
      passed: false,
      details: "All cards rendered within 60s"
    },
    {
      id: "determinism_check",
      name: "Determinism Check",
      required: false,
      passed: false,
      details: "Fixture hash matches expected"
    }
  ];
}
