export const runtime = "nodejs";

import { getJobIdForThread } from "@/lib/threadJobMapping";

export async function GET(
  request: Request,
  { params }: { params: { id: string } }
) {
  const { id: threadId } = params;

  // Check if backend is available
  if (!process.env.API_URL) {
    return new Response("Backend not available", { status: 503 });
  }

  try {
    // Get the current job ID for this thread
    let currentJobId = getJobIdForThread(threadId);
    console.log(`Thread ${threadId} mapped to job: ${currentJobId || 'none'}`);
    
    // If no mapping exists, try to find the latest job for this thread
    if (!currentJobId) {
      try {
        const jobsResp = await fetch(`${process.env.API_URL}/api/jobs`, {
          method: 'GET',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
          }
        });
        
        console.log(`Jobs API response: ${jobsResp.status} ${jobsResp.statusText}`);
        
        if (jobsResp.ok) {
          const jobs = await jobsResp.json();
          console.log(`Found ${jobs.length} jobs`);
          
          // Find the most recent job for this thread
          const threadJob = jobs.find((job: any) => 
            job.metadata?.threadId === threadId || 
            job.goal?.includes(threadId) ||
            job.id === threadId
          );
          if (threadJob) {
            currentJobId = threadJob.id;
            console.log(`Mapped thread ${threadId} to job ${currentJobId}`);
            // Store the mapping for future requests
            const { storeThreadJobMapping } = await import("@/lib/threadJobMapping");
            storeThreadJobMapping(threadId, currentJobId);
          }
        } else {
          console.warn(`Jobs API failed: ${jobsResp.status} ${jobsResp.statusText}`);
          const errorText = await jobsResp.text();
          console.warn(`Error response: ${errorText}`);
        }
      } catch (error) {
        console.warn("Could not fetch jobs list:", error);
      }
    }
    
    // If we have a job ID, stream its events
    if (currentJobId) {
      try {
        console.log(`Attempting to stream from job ${currentJobId}`);
        // Stream from the real job events endpoint
        const upstream = await fetch(
          `${process.env.API_URL}/api/jobs/${currentJobId}/events`,
          {
            headers: { Accept: "text/event-stream" },
            signal: request.signal,
          }
        );
        
        console.log(`Job events response: ${upstream.status} ${upstream.statusText}`);
        
        if (upstream.ok) {
          // Transform job events to chat events
          const transformStream = new TransformStream({
            transform(chunk, controller) {
              const decoder = new TextDecoder();
              const text = decoder.decode(chunk);
              
              // Parse SSE format: "data: {...}\n\n"
              const lines = text.split('\n');
              for (const line of lines) {
                if (line.startsWith('data: ')) {
                  try {
                    const jobEvent = JSON.parse(line.slice(6));
                    
                    // Transform job event to chat event format
                    const chatEvent = {
                      kind: "event",
                      event: {
                        ts: jobEvent.timestamp,
                        node: extractNodeFromEvent(jobEvent),
                        status: extractStatusFromEvent(jobEvent),
                        latencyMs: jobEvent.data?.latency_ms,
                        costUSD: jobEvent.data?.cost_usd,
                        msg: jobEvent.data?.message || jobEvent.event
                      }
                    };
                    
                    const transformed = `data: ${JSON.stringify(chatEvent)}\n\n`;
                    controller.enqueue(new TextEncoder().encode(transformed));
                  } catch (error) {
                    // Pass through malformed events
                    controller.enqueue(chunk);
                  }
                } else if (line.trim()) {
                  // Pass through non-data lines (comments, etc.)
                  controller.enqueue(new TextEncoder().encode(line + '\n'));
                }
              }
            }
          });
          
          return new Response(upstream.body?.pipeThrough(transformStream), {
            status: upstream.status,
            headers: {
              "Content-Type": "text/event-stream",
              "Cache-Control": "no-cache",
              "Connection": "keep-alive",
            },
          });
        } else {
          console.warn(`Job events endpoint failed: ${upstream.status} ${upstream.statusText}`);
          return new Response(`Job events not available: ${upstream.statusText}`, { status: upstream.status });
        }
      } catch (error) {
        console.warn(`Error connecting to job events: ${error}`);
        return new Response("Error connecting to job events", { status: 500 });
      }
    } else {
      console.log(`No job ID found for thread ${threadId}`);
      return new Response("No active job for this thread", { status: 404 });
    }
  } catch (error) {
    console.error("Backend SSE error:", error);
    return new Response("Internal server error", { status: 500 });
  }
}

// Helper functions to extract info from job events
function extractNodeFromEvent(jobEvent: any): string {
  if (jobEvent.data?.node) return jobEvent.data.node;
  if (jobEvent.data?.current_tool) return jobEvent.data.current_tool;
  if (jobEvent.event?.includes('github')) return 'github_enrichment';
  if (jobEvent.event?.includes('email')) return 'email_processing';
  if (jobEvent.event?.includes('crm')) return 'crm_sync';
  return jobEvent.event || 'unknown';
}

function extractStatusFromEvent(jobEvent: any): string {
  if (jobEvent.event?.includes('start') || jobEvent.event?.includes('begin')) return 'start';
  if (jobEvent.event?.includes('completed') || jobEvent.event?.includes('finished')) return 'ok';
  if (jobEvent.event?.includes('error') || jobEvent.event?.includes('failed')) return 'error';
  if (jobEvent.event?.includes('retry')) return 'retry';
  return 'ok';
}