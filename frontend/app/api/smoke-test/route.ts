export const runtime = "nodejs";

import { storeThreadJobMapping } from "@/lib/threadJobMapping";
import { SMOKE_TEST_FIXTURES } from "@/lib/smokeTestFixtures";

async function buildSmokeGoalFromYaml(): Promise<{ goal: string; params: any }> {
  try {
    // Fetch YAML from backend so server can keep canonical prompt config alongside agent
    const url = `${process.env.API_URL}/static/config/smoke_prompt.yaml`;
    const resp = await fetch(url, { cache: "no-store" });
    if (!resp.ok) throw new Error(`Failed to fetch smoke_prompt.yaml: ${resp.status}`);
    const text = await resp.text();
    // Minimal YAML parse to JSON (avoid heavy deps): rely on backend to keep JSON available too
    // Try to parse as YAML if available; otherwise, the backend can expose a JSON mirror later
    let doc: any = {};
    try {
      const { load } = await import("js-yaml");
      doc = load(text) as any;
    } catch {
      // Fallback: naive parse for key: value pairs
      doc = {};
    }

    const params = doc?.params || {};
    const language = params.language || "Python";
    const stars = params.stars_range || "1000..3000";
    const activity = Number(params.activity_days || 30);
    const target = Number(params.target_leads || 5);
    const budget = Number(params.budget_per_day || 10);
    let pushedSince = doc?.pushed_since;
    if (!pushedSince) {
      const d = new Date();
      d.setDate(d.getDate() - activity);
      pushedSince = d.toISOString().slice(0, 10);
    }

    const tpl = doc?.goal_template ||
      "Find maintainers of {{language}} repos stars:{{stars_range}} pushed:>= {{pushed_since}}; prioritize active {{activity_days}} days; export CSV.";
    const goal = tpl
      .replace(/{{language}}/g, language)
      .replace(/{{stars_range}}/g, stars)
      .replace(/{{pushed_since}}/g, pushedSince)
      .replace(/{{activity_days}}/g, String(activity));

    return { goal, params: { language, stars, activity, target, budget, pushedSince } };
  } catch (e) {
    // Fallback: hardcoded safe goal
    return { goal: "Find maintainers of Python repos stars:1000..3000 pushed:>=2025-06-01; prioritize active 90 days; export CSV.", params: {} };
  }
}

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId } = body;

    // Create smoke test job in the CMO Agent backend
    if (process.env.API_URL) {
      try {
        const built = await buildSmokeGoalFromYaml();
        const smokeJobPayload = {
          goal: built.goal,
          dryRun: false, // Make it a REAL run so we can see live progress
          config_path: null, // Use default config for real execution
          metadata: {
            threadId,
            autopilot_level: 0, // L0 for safety but real execution
            autonomy_level: "L0",
            budget_per_day: (built.params?.budget ?? 10), // Small budget for real run
            created_by: "smoke_test_real",
            test_type: "smoke_test_real",
            campaign_type: "smoke_test",
            max_leads: (built.params?.target ?? 5), // Limit scope for quick test
            created_at: new Date().toISOString()
          },
          // Pass prompt params to config so agent can early-stop when target met
          config: built.params ? { prompt_params: {
            target_leads: built.params.target,
            language: built.params.language,
            stars_range: built.params.stars,
            activity_days: built.params.activity,
            budget_per_day: built.params.budget,
            pushed_since: built.params.pushedSince,
          }} : undefined
        };

        console.log(`Creating smoke test job for thread: ${threadId}`);
        console.log(`Smoke test payload:`, JSON.stringify(smokeJobPayload, null, 2));

        const resp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(smokeJobPayload),
        });

        if (resp.ok) {
          const jobResult = await resp.json();

          // Store the mapping so the events endpoint knows which job to stream
          const actualJobId = jobResult.job_id || jobResult.id;
          console.log(`Smoke test job result:`, jobResult);
          console.log(`Storing smoke test mapping: ${threadId} -> ${actualJobId}`);
          storeThreadJobMapping(threadId, actualJobId);

          return new Response(JSON.stringify({
            success: true,
            jobId: actualJobId,
            threadId,
            message: `Smoke test ${actualJobId} started. Running vertical slice validation...`,
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
