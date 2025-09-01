// Type definitions for the CMO Agent frontend

export interface ActionButton {
  id: string;
  label: string;
  action: string;
  variant?: 'primary' | 'secondary' | 'danger' | 'success';
  disabled?: boolean;
}

export interface PolicyDiffCard {
  type: 'policy_diff';
  title: string;
  description?: string;
  changes: Array<{
    field: string;
    oldValue: any;
    newValue: any;
    impact?: string;
    type: 'added' | 'removed' | 'modified';
  }>;
  actions?: ActionButton[];
}

export interface SmokeTestCheck {
  id: string;
  name: string;
  status: 'passed' | 'failed' | 'running' | 'pending';
  message?: string;
  duration?: number;
}

export interface SmokeTestResultsCard {
  type: 'smoke_test_results';
  status: 'passed' | 'failed' | 'running';
  duration?: number;
  checks: SmokeTestCheck[];
  actions?: ActionButton[];
}

export interface ChatMessage {
  id: string;
  threadId: string;
  role: 'user' | 'assistant' | 'system' | 'tool';
  createdAt: string;
  text?: string;
  content?: string; // backward compatibility
  timestamp?: string; // backward compatibility
  event?: {
    node?: string;
    status?: string;
    latencyMs?: number;
    costUSD?: number;
    msg?: string;
  };
  card?: { type: string; [key: string]: any };
}

export interface SSEEvent {
  kind: 'message' | 'event' | 'status';
  message?: ChatMessage;
  event?: {
    status?: string;
    node?: string;
    msg?: string;
    costUSD?: number;
    latencyMs?: number;
  };
  status?: { closed?: boolean };
}

export type LanggraphEvent = any;

export interface JobEvent {
  type: string;
  data: any;
  timestamp: string;
  job_id: string;
}

export interface Job {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  goal: string;
  metadata: {
    threadId?: string;
    autonomy_level?: number;
    budget_per_day?: number;
    created_by?: string;
  };
  created_at: string;
  updated_at?: string;
}
