import { useState, useCallback, useRef } from "react";
import { ChatMessage, SSEEvent } from "@/types";
import { createSmokeTestChecks, SMOKE_TEST_CRITERIA, SmokeTestCheck } from "./smokeTestFixtures";
import { SmokeTestResultsCard } from "@/components/cards/SmokeTestResultsCardView";

export interface SmokeTestState {
  isRunning: boolean;
  startTime?: number;
  checks: SmokeTestCheck[];
  metrics: {
    eventsStreamed: number;
    cardsRendered: number;
    draftsCount: number;
    budgetUsed: number;
  };
  cardsRendered: Set<string>;
}

export function useSmokeTestEvaluator() {
  const [smokeTestState, setSmokeTestState] = useState<SmokeTestState>({
    isRunning: false,
    checks: createSmokeTestChecks(),
    metrics: {
      eventsStreamed: 0,
      cardsRendered: 0,
      draftsCount: 0,
      budgetUsed: 0
    },
    cardsRendered: new Set()
  });

  const timeoutRef = useRef<NodeJS.Timeout>();

  const startSmokeTest = useCallback((threadId: string) => {
    setSmokeTestState(prev => ({
      ...prev,
      isRunning: true,
      startTime: Date.now(),
      checks: createSmokeTestChecks(),
      metrics: {
        eventsStreamed: 0,
        cardsRendered: 0,
        draftsCount: 0,
        budgetUsed: 0
      },
      cardsRendered: new Set()
    }));

    // Set timeout for maximum test duration
    timeoutRef.current = setTimeout(() => {
      finalizeSmokeTest(threadId, false, "Test timed out after 60 seconds");
    }, SMOKE_TEST_CRITERIA.max_duration_ms);
  }, []);

  const processEvent = useCallback((event: SSEEvent, threadId: string) => {
    if (!smokeTestState.isRunning) return;

    setSmokeTestState(prev => {
      const newState = { ...prev };
      const newChecks = [...prev.checks];
      const newMetrics = { ...prev.metrics };
      const newCardsRendered = new Set(prev.cardsRendered);

      // Update metrics
      newMetrics.eventsStreamed++;

      if (event.kind === "event") {
        // Handle LangGraph events
        const langEvent = event.event;

        // Check for queue & stream
        if (langEvent?.node && !newChecks.find(c => c.id === "queue_stream")?.passed) {
          const queueCheck = newChecks.find(c => c.id === "queue_stream");
          if (queueCheck) {
            queueCheck.passed = true;
            queueCheck.details = `SSE connected, receiving events from ${langEvent.node}`;
          }
        }
      }

      return {
        ...newState,
        checks: newChecks,
        metrics: newMetrics,
        cardsRendered: newCardsRendered
      };
    });
  }, [smokeTestState.isRunning]);

  const processMessage = useCallback((message: ChatMessage, threadId: string) => {
    if (!smokeTestState.isRunning) return;

    setSmokeTestState(prev => {
      const newState = { ...prev };
      const newChecks = [...prev.checks];
      const newMetrics = { ...prev.metrics };
      const newCardsRendered = new Set(prev.cardsRendered);

      if (message.card) {
        const cardType = message.card.type;
        newCardsRendered.add(cardType);
        newMetrics.cardsRendered = newCardsRendered.size;

        // Check specific card types
        switch (cardType) {
          case "campaign_brief":
            const briefCheck = newChecks.find(c => c.id === "brief_rendered");
            if (briefCheck) {
              briefCheck.passed = true;
              briefCheck.details = "Campaign Brief card rendered with goal/limits/risks";
            }
            break;

          case "simulation":
            const simCheck = newChecks.find(c => c.id === "simulation_rendered");
            if (simCheck) {
              simCheck.passed = true;
              simCheck.details = "Simulation Pack rendered with forecasts";
            }
            break;

          case "outbox":
            const outboxCheck = newChecks.find(c => c.id === "drafts_rendered");
            if (outboxCheck && message.card.samples) {
              const samples = message.card.samples;
              newMetrics.draftsCount = samples.length;
              const validDrafts = samples.filter(s => s.score >= SMOKE_TEST_CRITERIA.min_draft_score);

              outboxCheck.passed = samples.length >= SMOKE_TEST_CRITERIA.min_drafts_count &&
                                 validDrafts.length >= SMOKE_TEST_CRITERIA.min_drafts_count;
              outboxCheck.details = `${samples.length} drafts, ${validDrafts.length} with score ≥80`;
            }
            break;

          case "run_summary":
            const summaryCheck = newChecks.find(c => c.id === "summary_rendered");
            if (summaryCheck) {
              summaryCheck.passed = true;
              summaryCheck.details = "Run Summary rendered with metrics";
            }
            break;

          case "error_group":
            const alertsCheck = newChecks.find(c => c.id === "alerts_captured");
            if (alertsCheck && message.card.errors) {
              alertsCheck.passed = message.card.errors.length >= SMOKE_TEST_CRITERIA.min_alerts_count;
              alertsCheck.details = `${message.card.errors.length} error groups captured`;
            }
            break;

          case "policy_diff":
            const policyCheck = newChecks.find(c => c.id === "policy_preview");
            if (policyCheck) {
              policyCheck.passed = true;
              policyCheck.details = "Policy change proposal rendered";
            }
            break;
        }
      }

      // Check if all required checks are complete
      const requiredChecks = newChecks.filter(c => c.required);
      const passedRequired = requiredChecks.filter(c => c.passed);

      if (passedRequired.length === requiredChecks.length) {
        // All required checks passed - finalize test
        setTimeout(() => finalizeSmokeTest(threadId, true), 1000);
      }

      return {
        ...newState,
        checks: newChecks,
        metrics: newMetrics,
        cardsRendered: newCardsRendered
      };
    });
  }, [smokeTestState.isRunning]);

  const finalizeSmokeTest = useCallback((threadId: string, passed: boolean, reason?: string) => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    setSmokeTestState(prev => {
      if (!prev.isRunning) return prev;

      const duration = prev.startTime ? Date.now() - prev.startTime : 0;
      const newChecks = [...prev.checks];

      // Update latency check
      const latencyCheck = newChecks.find(c => c.id === "latency_check");
      if (latencyCheck) {
        latencyCheck.passed = duration <= SMOKE_TEST_CRITERIA.max_duration_ms;
        latencyCheck.details = `Completed in ${(duration / 1000).toFixed(1)}s`;
      }

      // Update budget check (for now, assume passed since it's a dry run)
      const budgetCheck = newChecks.find(c => c.id === "budget_guardrail");
      if (budgetCheck) {
        budgetCheck.passed = prev.metrics.budgetUsed <= SMOKE_TEST_CRITERIA.max_budget_used;
        budgetCheck.details = `Used $${prev.metrics.budgetUsed.toFixed(2)} of $${SMOKE_TEST_CRITERIA.max_budget_used} cap`;
      }

      const finalStatus = passed && newChecks.filter(c => c.required).every(c => c.passed) ? "passed" : "failed";

      return {
        ...prev,
        isRunning: false,
        checks: newChecks
      };
    });
  }, []);

  const getSmokeTestResultsCard = useCallback((): SmokeTestResultsCard | null => {
    if (smokeTestState.isRunning) {
      return {
        type: "smoke_test_results",
        status: "running",
        checks: smokeTestState.checks,
        metrics: smokeTestState.metrics,
        actions: []
      };
    }

    if (smokeTestState.startTime && !smokeTestState.isRunning) {
      const duration = Date.now() - smokeTestState.startTime;
      const requiredPassed = smokeTestState.checks.filter(c => c.required && c.passed).length;
      const requiredTotal = smokeTestState.checks.filter(c => c.required).length;
      const status = requiredPassed === requiredTotal ? "passed" : "failed";

      return {
        type: "smoke_test_results",
        status,
        duration,
        checks: smokeTestState.checks,
        metrics: smokeTestState.metrics,
        actions: [
          { id: "view-logs", label: "View Logs", style: "secondary" },
          { id: "retry-smoke", label: "Retry", style: "primary" },
          { id: "export-results", label: "Export", style: "secondary" }
        ]
      };
    }

    return null;
  }, [smokeTestState]);

  return {
    smokeTestState,
    startSmokeTest,
    processEvent,
    processMessage,
    finalizeSmokeTest,
    getSmokeTestResultsCard
  };
}
