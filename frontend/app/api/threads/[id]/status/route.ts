export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";
import { getThread } from "@/lib/threadStorage";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;

  try {
    // Get thread info and current job
    const thread = getThread(threadId);
    const currentJobId = getJobIdForThread(threadId) || thread?.currentJobId;

    let jobStatus = null;
    
    // If we have a job ID and backend is available, get real job status
    if (currentJobId && process.env.API_URL) {
      try {
        // Try to get job status from backend (this endpoint may not exist yet)
        const jobResponse = await fetch(`${process.env.API_URL}/api/jobs/${currentJobId}/status`);
        
        if (jobResponse.ok) {
          jobStatus = await jobResponse.json();
        }
      } catch (error) {
        console.warn("Could not fetch job status:", error);
      }
    }

    return new Response(JSON.stringify({
      threadId,
      currentJobId,
      thread,
      jobStatus,
      hasActiveJob: !!currentJobId,
      timestamp: new Date().toISOString()
    }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });

  } catch (error) {
    console.error("Thread status API error:", error);
    return new Response(
      JSON.stringify({ 
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
