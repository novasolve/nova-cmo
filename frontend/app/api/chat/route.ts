export const runtime = "nodejs";

import { storeThreadJobMapping } from "@/lib/threadJobMapping";
import { autonomyToAutopilot, type AutonomyLevel } from "@/lib/autonomy";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId, text, options } = body;
    
    // Convert autonomy level to numeric autopilot for backend compatibility
    const autopilot = options?.autonomy ? autonomyToAutopilot(options.autonomy) : 0;

    // Create a job in the CMO Agent backend
    if (process.env.API_URL) {
      try {
        // Detect if this is a smoke test
        const isSmokeTest = text.toLowerCase().includes('smoke test');
        
        const jobPayload = {
          goal: text,
          dryRun: autopilot === 0, // L0 = dry run, L1+ = real execution
          config_path: isSmokeTest ? "cmo_agent/config/smoke.yaml" : null,
          metadata: {
            threadId,
            autopilot_level: autopilot,
            autonomy_level: options?.autonomy || "L0",
            budget_per_day: options?.budget || 50,
            created_by: "chat_console",
            test_type: isSmokeTest ? "smoke_test" : "regular",
            created_at: new Date().toISOString()
          }
        };

        const resp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(jobPayload),
        });
        
        if (resp.ok) {
          const jobResult = await resp.json();
          
          // Store the mapping so the events endpoint knows which job to stream
          storeThreadJobMapping(threadId, jobResult.id);
          
          return new Response(JSON.stringify({
            success: true,
            jobId: jobResult.id,
            threadId,
            message: `Job ${jobResult.id} created and ${jobResult.status}. Streaming events...`,
            timestamp: new Date().toISOString()
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

    // No backend configured
    return new Response(JSON.stringify({
      success: false,
      error: "No backend configured. Set API_URL environment variable.",
      threadId,
      timestamp: new Date().toISOString()
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Chat API error:", error);
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
