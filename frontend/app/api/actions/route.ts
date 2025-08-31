export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";

export async function POST(req: Request) {
  try {
    const body = await req.json();
    const { threadId, actionId, payload } = body;

    // Get the job ID for this thread
    const jobId = getJobIdForThread(threadId);
    
    if (!jobId) {
      return new Response(JSON.stringify({
        success: false,
        error: "No active job for this thread"
      }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      });
    }

    // Handle different action types
    if (process.env.API_URL) {
      try {
        let endpoint = "";
        let method = "POST";
        let requestBody = {};

        switch (actionId) {
          case "pause":
          case "pause-job":
            endpoint = `/api/jobs/${jobId}/pause`;
            break;
          case "resume":
          case "resume-job":
            endpoint = `/api/jobs/${jobId}/resume`;
            break;
          case "cancel":
          case "cancel-job":
            endpoint = `/api/jobs/${jobId}/cancel`;
            break;
          case "simulate":
          case "run-l1":
          case "run-l2":
          case "run-l3":
          case "run-l4":
            // These would trigger new jobs or modify existing ones
            // For now, just acknowledge the action
            return new Response(JSON.stringify({
              success: true,
              message: `Action ${actionId} acknowledged for job ${jobId}`,
              timestamp: new Date().toISOString()
            }), {
              status: 200,
              headers: { "Content-Type": "application/json" },
            });
          default:
            return new Response(JSON.stringify({
              success: false,
              error: `Unknown action: ${actionId}`
            }), {
              status: 400,
              headers: { "Content-Type": "application/json" },
            });
        }

        const resp = await fetch(`${process.env.API_URL}${endpoint}`, {
          method,
          headers: { "Content-Type": "application/json" },
          body: Object.keys(requestBody).length > 0 ? JSON.stringify(requestBody) : undefined,
        });
        
        if (resp.ok) {
          const result = await resp.json();
          return new Response(JSON.stringify({
            success: true,
            message: `Action ${actionId} completed successfully`,
            result,
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
        console.error("Backend action failed:", error);
        return new Response(JSON.stringify({
          success: false,
          error: `Backend unavailable: ${error instanceof Error ? error.message : String(error)}`,
          timestamp: new Date().toISOString()
        }), {
          status: 503,
          headers: { "Content-Type": "application/json" },
        });
      }
    }

    return new Response(JSON.stringify({
      success: false,
      error: "No backend configured"
    }), {
      status: 500,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Actions API error:", error);
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
