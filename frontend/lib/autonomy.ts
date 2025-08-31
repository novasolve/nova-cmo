// Autonomy levels and UI configuration
export type AutonomyLevel = "L0" | "L1" | "L2" | "L3" | "L4";

export const AUTONOMY = {
  L0: {
    chip: "Co‑pilot",
    label: "Co‑pilot",
    tooltip: "Review every step; nothing sends without your approval.",
    description: "Manual review of all actions before execution",
    risk: "zero"
  },
  L1: {
    chip: "Guarded", 
    label: "Guarded",
    tooltip: "Runs routine steps; pauses at checkpoints (send/CRM).",
    description: "Automated execution with approval gates at critical steps",
    risk: "low"
  },
  L2: {
    chip: "Autopilot",
    label: "Autopilot", 
    tooltip: "End‑to‑end run within budget & policy guardrails.",
    description: "Full automation within defined constraints",
    risk: "medium"
  },
  L3: {
    chip: "L3",
    label: "Self-tuning",
    tooltip: "Self-tuning: Adjust within policy", 
    description: "Adjusts pacing/variants/filters within policies",
    risk: "high"
  },
  L4: {
    chip: "L4",
    label: "Advanced",
    tooltip: "Fully autonomous with reports",
    description: "Complete automation with periodic reports",
    risk: "maximum"
  }
} as const;

export const AUTONOMY_ICONS = {
  L0: "🤝",
  L1: "🛡️", 
  L2: "🚀",
  L3: "🔧",
  L4: "🤖"
} as const;

export const AUTONOMY_COLORS = {
  L0: "bg-gray-100 text-gray-800 border-gray-300",
  L1: "bg-blue-100 text-blue-800 border-blue-300",
  L2: "bg-green-100 text-green-800 border-green-300", 
  L3: "bg-yellow-100 text-yellow-800 border-yellow-300",
  L4: "bg-red-100 text-red-800 border-red-300"
} as const;

// Ordered by usage frequency: most used → least used
export const QUICK_ACTIONS = {
  plan: {
    id: "plan",
    label: "Plan",
    tooltip: "Generate campaign brief + YAML config."
  },
  simulate: {
    id: "simulate", 
    label: "Simulate",
    tooltip: "Run forecasts and risk checks before sending."
  },
  drafts: {
    id: "drafts",
    label: "Drafts", 
    tooltip: "Review and edit sample emails."
  },
  alerts: {
    id: "alerts",
    label: "Alerts",
    tooltip: "Issues that need attention (errors, warnings)."
  },
  smoke_test: {
    id: "smoke_test",
    label: "Self‑Test", 
    tooltip: "Real 5-lead Python campaign to validate pipeline. Live progress in Inspector."
  },
  guide: {
    id: "guide",
    label: "Guide",
    tooltip: "Step‑by‑step walkthrough of the console."
  },
  demo_mode: {
    id: "demo_mode",
    label: "Demo Mode",
    tooltip: "Switch to sample data and canned runs."
  }
} as const;

export const ACTIONS = {
  // Job control actions
  pause: { id: "pause", label: "Pause", style: "secondary" as const },
  resume: { id: "resume", label: "Resume", style: "primary" as const },
  cancel: { id: "cancel", label: "Cancel", style: "danger" as const },
  
  // Job creation/execution 
  runJob: { id: "run-job", label: "Run Job", style: "primary" as const },
  launchCampaign: { id: "launch-campaign", label: "Launch Campaign", style: "primary" as const },
  launchAgent: { id: "launch-agent", label: "Launch Agent", style: "primary" as const },
  
  // Campaign actions with autonomy modes
  runManual: { id: "run-manual", label: "Start in Manual Mode", style: "secondary" as const },
  runAssisted: { id: "run-assisted", label: "Start in Assisted Mode", style: "primary" as const },
  runAutonomous: { id: "run-autonomous", label: "Start in Autonomous Mode", style: "primary" as const },
  
  // Approval actions
  approve: { id: "approve", label: "Approve", style: "primary" as const },
  approveAll80: { id: "approve-all-80", label: "Approve ≥ 80", style: "primary" as const },
  edit: { id: "edit", label: "Edit", style: "secondary" as const },
  skip: { id: "skip", label: "Skip", style: "secondary" as const },
  
  // Export actions
  downloadCsv: { id: "download-csv", label: "Download CSV", style: "secondary" as const },
  downloadPdf: { id: "download-pdf", label: "Download PDF", style: "secondary" as const },
  exportJson: { id: "export-json", label: "Export JSON", style: "secondary" as const },
  
  // Workflow navigation
  next: { id: "next", label: "Next", style: "primary" as const },
  back: { id: "back", label: "Back", style: "secondary" as const },
  confirm: { id: "confirm", label: "Confirm", style: "primary" as const },
  finishAndLaunch: { id: "finish-launch", label: "Finish and Launch", style: "primary" as const },
  
  // Smoke test actions
  viewLogs: { id: "view-logs", label: "View Logs", style: "secondary" as const },
  retrySmoke: { id: "retry-smoke", label: "Retry", style: "primary" as const }
} as const;

// Helper to convert autonomy level to autopilot number for backend compatibility
export function autonomyToAutopilot(autonomy: AutonomyLevel): number {
  switch (autonomy) {
    case "L0": return 0;
    case "L1": return 1; 
    case "L2": return 2;
    case "L3": return 3;
    case "L4": return 4;
    default: return 0;
  }
}

// Helper to convert autopilot number to autonomy level
export function autopilotToAutonomy(autopilot: number): AutonomyLevel {
  switch (autopilot) {
    case 0: return "L0";
    case 1: return "L1";
    case 2: return "L2"; 
    case 3: return "L3";
    case 4: return "L4";
    default: return "L0";
  }
}