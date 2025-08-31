export const runtime = "nodejs";

import { storeThreadJobMapping } from "@/lib/threadJobMapping";
import { SMOKE_TEST_FIXTURES } from "@/lib/smokeTestFixtures";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId } = body;

    // Create smoke test job in the CMO Agent backend
    if (process.env.API_URL) {
      try {
        const smokeJobPayload = {
          goal: "Find 5 active Python maintainers from the last 30 days for smoke test validation",
          dryRun: false, // Make it a REAL run so we can see live progress
          config_path: null, // Use default config for real execution
          metadata: {
            threadId,
            autopilot_level: 0, // L0 for safety but real execution
            autonomy_level: "L0",
            budget_per_day: 10, // Small budget for real run
            created_by: "smoke_test_real",
            test_type: "smoke_test_real",
            campaign_type: "smoke_test",
            max_leads: 5, // Limit scope for quick test
            created_at: new Date().toISOString()
          }
        };

        const resp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(smokeJobPayload),
        });
        
        if (resp.ok) {
          const jobResult = await resp.json();
          
          // Store the mapping so the events endpoint knows which job to stream
          storeThreadJobMapping(threadId, jobResult.id);
          
          return new Response(JSON.stringify({
            success: true,
            jobId: jobResult.id,
            threadId,
            message: `Smoke test ${jobResult.id} started. Running vertical slice validation...`,
            testType: "smoke_test",
            startTime: new Date().toISOString()
          }), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          });
        } else {
          const errorText = await resp.text();
          throw new Error(`Backend error: ${errorText}`);
        }
      } catch (error) {
        console.error("Backend connection failed:", error);
        
        // Return error response
        return new Response(JSON.stringify({
          success: false,
          error: `Backend unavailable: ${error instanceof Error ? error.message : String(error)}`,
          threadId,
          timestamp: new Date().toISOString()
        }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    // No backend configured - run mock smoke test
    return new Response(JSON.stringify({
      success: true,
      jobId: "smoke-mock-" + Date.now(),
      threadId,
      message: "Mock smoke test started (no backend configured)",
      testType: "smoke_test_mock",
      startTime: new Date().toISOString()
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Smoke test API error:", error);
    return new Response(
      JSON.stringify({ 
        success: false,
        error: "Internal server error",
        timestamp: new Date().toISOString()
      }),
      { 
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    );
  }
}
